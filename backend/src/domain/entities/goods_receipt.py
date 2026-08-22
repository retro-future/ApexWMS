"""Goods arriving, and the rules that decide whether they may (PRD §4.4, §5.3).

This is the aggregate PRD §7.3 names as the worked example: a receipt and
its lines are one consistency boundary, so they load, validate and save as
a unit. **Every rule below is a pure function of the receipt's own lines** —
no catalog lookup, no database, no tenant. That is what lets the whole of
FR-3.8 and FR-3.10 be tested with nothing running.

Two facts here are deliberately independent of each other:

- ``acquisition_source`` is about the **document**: goods came from a
  supplier, or were bought from a walk-in customer (FR-3.3b).
- ``condition`` is about each **handset**: new, refurbished, or used.

Nothing couples them. A supplier delivers used stock, and a walk-in
occasionally brings in a sealed phone. Used stock reaches the store both
ways, and a rule tying one to the other would refuse a real delivery.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.entities.document import Document
from domain.enums import AcquisitionSource, DeviceCondition, TrackingType
from domain.errors import (
    CurrencyMismatchError,
    DuplicateScanError,
    InvalidLineError,
    InvalidMoneyError,
    ReceiptIncompleteError,
    ReceiptSourceError,
    UnpricedUnitError,
)
from domain.value_objects import IMEI, Currency, Money


@dataclass(eq=False, kw_only=True)
class ReceivedUnit(UuidEntity, TenantEntity):
    """One scanned handset, as it stands while the receipt is still a draft.

    ``acquisition_cost`` and ``asking_price`` are nullable *here* and not
    on ``DeviceUnit``, and that gap is the workflow: a Storekeeper scans
    IMEIs and states condition, an Owner or Manager states what was paid
    and what it is offered at (FR-3.4b). A draft may sit unpriced
    indefinitely; confirm is where that stops being allowed (FR-3.12).
    """

    goods_receipt_line_id: UUID
    imei: IMEI
    imei2: IMEI | None = None
    serial_number: str | None = None
    condition: DeviceCondition
    acquisition_cost: Money | None = None
    asking_price: Money | None = None
    # The som actually handed to a walk-in against a USD catalog row
    # (§4.5b). A bare pair and never a ``Money``, so it cannot join a total.
    cash_paid_minor: int | None = None
    cash_paid_currency: Currency | None = None

    def __post_init__(self) -> None:
        if self.acquisition_cost is not None and self.acquisition_cost.is_negative:
            raise InvalidMoneyError("an acquisition cost may not be negative")
        if self.asking_price is not None and self.asking_price.is_negative:
            raise InvalidMoneyError("an asking price may not be negative")
        if (
            self.acquisition_cost is not None
            and self.asking_price is not None
            and self.acquisition_cost.currency is not self.asking_price.currency
        ):
            raise CurrencyMismatchError(
                f"IMEI {self.imei} is bought in {self.acquisition_cost.currency.value} "
                f"and offered in {self.asking_price.currency.value}; a unit cannot be "
                "denominated differently from its product (§4.5 rule 3)"
            )
        if (self.cash_paid_minor is None) != (self.cash_paid_currency is None):
            raise InvalidMoneyError(
                "cash_paid needs both an amount and a currency, or neither"
            )

    @property
    def needs_asking_price(self) -> bool:
        """FR-3.10: only a ``NEW`` handset may reach the shelf unpriced.

        Everything else carries its own price or cannot be sold, because a
        used unit never inherits the catalog price (FR-2.14).
        """
        return self.condition is not DeviceCondition.NEW and self.asking_price is None


@dataclass(eq=False, kw_only=True)
class GoodsReceiptLine(UuidEntity, TenantEntity):
    goods_receipt_id: UUID
    product_id: UUID
    quantity: int
    # QUANTITY lines only. A serialized line prices each handset
    # individually, so a line cost there would be a stored value nothing
    # reads — see ``__post_init__``.
    unit_cost: Money | None = None
    # Both the product's, carried onto the line by the repository's join.
    # The currency is here rather than derived from ``unit_cost`` because a
    # serialized line has no line cost and may have no priced scan yet, and
    # a line still has to say what it will be denominated in.
    tracking_type: TrackingType
    currency: Currency
    units: list[ReceivedUnit] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise InvalidLineError(f"a line for {self.quantity} units receives nothing")
        if self.unit_cost is not None:
            if self.is_serial:
                raise InvalidLineError(
                    "a serialized line prices each handset individually (FR-3.4b) "
                    "and carries no line cost"
                )
            if self.unit_cost.is_negative:
                raise InvalidMoneyError("a unit cost may not be negative")
            if self.unit_cost.currency is not self.currency:
                raise CurrencyMismatchError(
                    f"line cost is {self.unit_cost.currency.value} but the product is "
                    f"priced in {self.currency.value} (§4.5 rule 3)"
                )

    @property
    def is_serial(self) -> bool:
        return self.tracking_type is TrackingType.SERIAL

    @property
    def total_cost(self) -> Money | None:
        """What this whole line cost, as one figure.

        For a quantity line that is ``unit_cost × quantity``; the ledger
        speaks in line totals, and ``CostPool.receive_total`` takes the
        figure whole rather than dividing it out and multiplying it back.
        """
        if self.is_serial:
            costs = [u.acquisition_cost for u in self.units if u.acquisition_cost is not None]
            if not costs:
                return None
            return sum(costs[1:], costs[0])
        if self.unit_cost is None:
            return None
        return self.unit_cost * self.quantity


@dataclass(eq=False, kw_only=True)
class GoodsReceipt(Document):
    acquisition_source: AcquisitionSource
    supplier_id: UUID | None = None
    # A trade-in may name the walk-in it was bought from; a PO never can.
    customer_id: UUID | None = None
    purchase_order_id: UUID | None = None
    location_id: UUID
    lines: list[GoodsReceiptLine] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Checked on construction, not only at confirm: FR-3.3b's test says
        # a SUPPLIER receipt with no supplier is rejected when it is saved,
        # while a trade-in with no supplier saves and confirms.
        self._assert_source_consistent()

    def confirm(self, now: datetime, user_id: UUID) -> None:
        """FR-3.7: everything that must be true before goods enter stock."""
        self.assert_editable()
        self._assert_source_consistent()
        self._assert_lines_complete()
        self._assert_priced()
        super().confirm(now, user_id)

    def units(self) -> list[ReceivedUnit]:
        return [unit for line in self.lines for unit in line.units]

    def subtotals(self) -> dict[Currency, Money]:
        """One figure per currency present, never their sum (FR-2.7).

        Skips whatever is still unpriced rather than refusing, because a
        draft is read while it is being filled in.
        """
        totals: dict[Currency, Money] = {}
        for line in self.lines:
            total = line.total_cost
            if total is None:
                continue
            running = totals.get(total.currency, Money.zero(total.currency))
            totals[total.currency] = running + total
        return totals

    def received_quantities(self) -> dict[UUID, int]:
        """How much of each product this receipt brought in — FR-3.9's numerator."""
        received: dict[UUID, int] = {}
        for line in self.lines:
            received[line.product_id] = received.get(line.product_id, 0) + line.quantity
        return received

    def _assert_source_consistent(self) -> None:
        if self.acquisition_source is AcquisitionSource.SUPPLIER:
            if self.supplier_id is None:
                raise ReceiptSourceError(
                    "a receipt from a supplier must name one (FR-3.3b)"
                )
            return

        if self.supplier_id is not None:
            raise ReceiptSourceError(
                "a trade-in is bought from a walk-in customer, not a supplier — "
                "it names no supplier (FR-3.3b)"
            )
        if self.purchase_order_id is not None:
            raise ReceiptSourceError(
                "a trade-in cannot be received against a purchase order — there is "
                "no order for a phone that walked in the door (FR-3.3b)"
            )

    def _assert_lines_complete(self) -> None:
        if not self.lines:
            raise ReceiptIncompleteError(f"{self.number} has no lines to receive")

        short = [
            f"{line.product_id}: {len(line.units)} of {line.quantity} scanned"
            for line in self.lines
            if line.is_serial and len(line.units) != line.quantity
        ]
        if short:
            raise ReceiptIncompleteError(
                f"{self.number} cannot be confirmed — {'; '.join(short)} (FR-3.8)"
            )

        scanned = Counter(str(unit.imei) for unit in self.units())
        repeated = sorted(imei for imei, count in scanned.items() if count > 1)
        if repeated:
            raise DuplicateScanError(
                f"{self.number} scans the same handset twice: {', '.join(repeated)}"
            )

        unpriced_lines = [
            str(line.product_id)
            for line in self.lines
            if not line.is_serial and line.unit_cost is None
        ]
        if unpriced_lines:
            raise UnpricedUnitError(
                f"{self.number} cannot be confirmed — no unit cost on "
                f"{', '.join(unpriced_lines)}"
            )

    def _assert_priced(self) -> None:
        """FR-3.10, naming every offending IMEI in one message.

        One pass, not one handset at a time: the person fixing this is
        holding a stack of phones, and a receipt that reveals its gaps one
        error at a time turns that into ten round trips.
        """
        costless = sorted(str(u.imei) for u in self.units() if u.acquisition_cost is None)
        if costless:
            raise UnpricedUnitError(
                f"{self.number} cannot be confirmed — no acquisition cost on "
                f"{', '.join(costless)} (FR-3.4b)"
            )

        unpriced = sorted(str(u.imei) for u in self.units() if u.needs_asking_price)
        if unpriced:
            raise UnpricedUnitError(
                f"{self.number} cannot be confirmed — these are not NEW and carry no "
                f"asking price: {', '.join(unpriced)} (FR-3.10)"
            )
