"""An intention to buy (PRD §4.4, FR-3.1).

A PO is a piece of paper sent to a supplier; goods arrive later, on a Goods
Receipt, and that is what writes the ledgers. Confirming a PO writes
nothing to either ledger — it only fixes the order's numbers, so the
supplier and the store are looking at the same figures.

The price on each line is not known when a line is first raised (an Owner
may want to record what it intends to buy before a supplier has quoted a
price). ``unit_cost`` is filled in afterward, while the order is still a
draft, and ``confirm`` is the point that requires every line to have one —
the same shape ``GoodsReceipt.confirm`` already enforces for its units. A
Goods Receipt may only be raised against a ``CONFIRMED`` order, so an
unpriced line can never reach one.

Each line takes its currency from its product (FR-2.7), so one order may
hold a USD phone line and a UZS accessory line at once. There is no
document-level currency and no combined total anywhere — ``subtotals``
returns one figure per currency present, side by side.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.entities.document import Document
from domain.enums import TrackingType
from domain.errors import (
    CurrencyMismatchError,
    InvalidLineError,
    InvalidMoneyError,
    UnpricedOrderLineError,
)
from domain.value_objects import Currency, Money


@dataclass(eq=False, kw_only=True)
class PurchaseOrderLine(UuidEntity, TenantEntity):
    purchase_order_id: UUID
    product_id: UUID
    quantity: int
    unit_cost: Money | None = None
    # The product's, carried onto the line by the repository's join so the
    # rules above need no catalog lookup of their own. Kept even while
    # ``unit_cost`` is still null, since the line has to say what it will
    # eventually be denominated in.
    currency: Currency
    tracking_type: TrackingType

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise InvalidLineError(f"a line for {self.quantity} units orders nothing")
        if self.unit_cost is not None:
            if self.unit_cost.is_negative:
                raise InvalidMoneyError("a unit cost may not be negative")
            if self.unit_cost.currency is not self.currency:
                raise CurrencyMismatchError(
                    f"line cost is {self.unit_cost.currency.value} but the product is "
                    f"priced in {self.currency.value} (§4.5 rule 3)"
                )

    @property
    def total_cost(self) -> Money | None:
        if self.unit_cost is None:
            return None
        return self.unit_cost * self.quantity


@dataclass(eq=False, kw_only=True)
class PurchaseOrder(Document):
    supplier_id: UUID
    lines: list[PurchaseOrderLine] = field(default_factory=list)

    def confirm(self, now: datetime, user_id: UUID) -> None:
        """FR-3.2: the deal is final, so every line must state its price."""
        self.assert_editable()
        self._assert_priced()
        super().confirm(now, user_id)

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

    def ordered_quantities(self) -> dict[UUID, int]:
        """How much of each product was ordered — FR-3.9's denominator."""
        ordered: dict[UUID, int] = {}
        for line in self.lines:
            ordered[line.product_id] = ordered.get(line.product_id, 0) + line.quantity
        return ordered

    def _assert_priced(self) -> None:
        unpriced = sorted(str(line.product_id) for line in self.lines if line.unit_cost is None)
        if unpriced:
            raise UnpricedOrderLineError(
                f"{self.number} cannot be confirmed — no unit cost on "
                f"{', '.join(unpriced)}"
            )
