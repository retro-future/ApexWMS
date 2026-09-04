"""Goods coming back from a customer (PRD §4.4, §5.4b).

Not a cancelled sale. Cancelling says the sale never should have happened
and reverses every line at its original price; a return says the sale stood
and part of it came back later, possibly at less than was charged. §5.10
reports the two in different columns, so they are two documents.

Not a ``RemovalLine`` either, for the reason that class states: nothing
leaves under a supplier return or a write-off *at a price*, and a refund is
a price. ``CustomerReturnLine`` therefore looks like a sales invoice line
rather than a removal one — an amount, an approver and a note.

Every rule here is a pure function of the return's own lines. Whether the
handset is still ``SOLD``, and whether this invoice line has been returned
before, both need live rows, so they belong to ``CustomerReturnPoster`` and
``ConfirmCustomerReturnHandler`` rather than here.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.entities.document import Document
from domain.enums import CustomerReturnReason, TrackingType
from domain.errors import (
    CurrencyMismatchError,
    DebtReliefError,
    DuplicateScanError,
    EmptyDocumentError,
    InvalidLineError,
    InvalidMoneyError,
    RefundExceedsChargeError,
    UnapprovedRefundError,
)
from domain.services.subtotals import SubtotalsCalculator
from domain.value_objects import Currency, Money


@dataclass(eq=False, kw_only=True)
class CustomerReturnLine(UuidEntity, TenantEntity):
    customer_return_id: UUID
    # The invoice line this unwinds. Every return names one, which is what
    # gives the refund its ceiling and the goods their original cost.
    sales_invoice_line_id: UUID
    product_id: UUID
    device_unit_id: UUID | None = None
    quantity: int = 1
    # The product's, carried onto the line by the repository's join.
    currency: Currency
    tracking_type: TrackingType
    # Both carried by the same join: the handset's IMEI, and what the sale
    # actually charged for one of these. Read-only.
    imei: str | None = None
    charged_price: Money
    # How many the invoice line sold. The ceiling on what may come back,
    # and the denominator when a partial return takes its share of the
    # cost the sale booked.
    sold_quantity: int
    refund_price: Money
    refund_approved_by: UUID | None = None
    refund_note: str | None = None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise InvalidLineError(f"a line for {self.quantity} units returns nothing")
        if self.is_serial:
            if self.device_unit_id is None:
                raise InvalidLineError(
                    "a serialized line must name the handset it returns"
                )
            if self.quantity != 1:
                raise InvalidLineError(
                    "a serialized line returns one named handset, so its quantity is 1"
                )
        elif self.device_unit_id is not None:
            raise InvalidLineError("a quantity line names no device unit (§4.1)")
        if self.quantity > self.sold_quantity:
            raise InvalidLineError(
                f"returning {self.quantity} of something the sale sold "
                f"{self.sold_quantity} of"
            )
        self._assert_refund()

    @property
    def is_serial(self) -> bool:
        return self.tracking_type is TrackingType.SERIAL

    @property
    def is_reduced(self) -> bool:
        """Whether the store is keeping part of what the customer paid."""
        return self.refund_price < self.charged_price

    @property
    def line_total(self) -> Money:
        return self.refund_price * self.quantity

    def count(self, quantity: int) -> None:
        """FR-4.5c's twin: correct a mis-scanned accessory count in place.

        Re-validates rather than assigning, so the ceiling — never more than
        the sale sold — stays stated in one place, and a refused value leaves
        the line as it was.
        """
        if self.is_serial:
            raise InvalidLineError(
                "a serialized line returns one named handset; unscan it instead"
            )
        previous = self.quantity
        self.quantity = quantity
        try:
            self.__post_init__()
        except Exception:
            self.quantity = previous
            raise

    def reduce_to(self, refund: Money, user_id: UUID, note: str) -> None:
        """FR-4.9c: a Manager keeps part of the price, and signs for it."""
        self.refund_price = refund
        self.refund_approved_by = user_id
        self.refund_note = note
        self._assert_refund()

    def _assert_refund(self) -> None:
        for label, amount in (
            ("charged", self.charged_price),
            ("refund", self.refund_price),
        ):
            if amount.currency is not self.currency:
                raise CurrencyMismatchError(
                    f"a {label} price is in {amount.currency.value} but the line is "
                    f"in {self.currency.value}"
                )
            if amount.is_negative:
                raise InvalidMoneyError(f"a {label} price may not be negative")
        if self.refund_price > self.charged_price:
            raise RefundExceedsChargeError(
                f"refunding {self.refund_price} for goods sold at "
                f"{self.charged_price} would pay back more than the sale took",
                refund=str(self.refund_price),
                charged=str(self.charged_price),
            )
        if self.is_reduced and (
            self.refund_approved_by is None or not self.refund_note
        ):
            raise UnapprovedRefundError(
                f"refunding {self.refund_price} instead of {self.charged_price} "
                "needs an approver and a note",
                refund=str(self.refund_price),
                charged=str(self.charged_price),
            )


@dataclass(eq=False, kw_only=True)
class CustomerReturn(Document):
    # Always set: goods with no sale behind them enter through a stock
    # count, which is the document that can say where they came from.
    sales_invoice_id: UUID
    # Copied from the invoice at creation. Null when the sale was to a
    # walk-in, exactly as the invoice allows (FR-4.1).
    customer_id: UUID | None = None
    location_id: UUID
    reason: CustomerReturnReason
    # Som, and never a conversion of the line refunds above (§4.7): a
    # store-credit debt is written directly in som, so the relief against it
    # is too. Null on a sale that opened no debt.
    debt_relief: Money | None = None
    lines: list[CustomerReturnLine] = field(default_factory=list)

    def confirm(self, now: datetime, user_id: UUID) -> None:
        """FR-4.9f: everything that must be true before goods come back."""
        self.assert_editable()
        self._assert_has_lines()
        self._assert_no_unit_twice()
        self._assert_relief()
        super().confirm(now, user_id)

    def subtotals(self) -> dict[Currency, Money]:
        """What is being paid back, one figure per currency, never summed."""
        return SubtotalsCalculator.by_currency(line.line_total for line in self.lines)

    def line_for_unit(self, device_unit_id: UUID) -> CustomerReturnLine | None:
        """The line already returning this handset — the idempotent re-scan (§6)."""
        return next(
            (line for line in self.lines if line.device_unit_id == device_unit_id),
            None,
        )

    def line_for_invoice_line(
        self, sales_invoice_line_id: UUID
    ) -> CustomerReturnLine | None:
        """The quantity line already unwinding this invoice line, if there is one."""
        return next(
            (
                line
                for line in self.lines
                if line.sales_invoice_line_id == sales_invoice_line_id
                and not line.is_serial
            ),
            None,
        )

    def _assert_has_lines(self) -> None:
        if not self.lines:
            raise EmptyDocumentError(
                f"{self.number} has no lines — nothing is coming back",
                number=self.number,
            )

    def _assert_no_unit_twice(self) -> None:
        seen: set[UUID] = set()
        for line in self.lines:
            if line.device_unit_id is None:
                continue
            if line.device_unit_id in seen:
                raise DuplicateScanError(
                    f"{self.number} returns the same handset twice — one phone, one line",
                    number=self.number,
                )
            seen.add(line.device_unit_id)

    def _assert_relief(self) -> None:
        if self.debt_relief is None:
            return
        if self.debt_relief.currency is not Currency.UZS:
            raise DebtReliefError(
                f"{self.number} relieves debt in {self.debt_relief.currency.value}, "
                "but all customer debt is som (§4.7)",
                key="relief_not_som",
                number=self.number,
            )
        if self.debt_relief.is_zero or self.debt_relief.is_negative:
            raise DebtReliefError(
                f"{self.number} states a debt relief of {self.debt_relief}, which "
                "settles nothing",
                key="relief_not_positive",
                number=self.number,
            )
