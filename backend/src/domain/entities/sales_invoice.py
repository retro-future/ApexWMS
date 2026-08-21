"""A sale to a customer (PRD §4.4, §5.4 — M5).

The outbound counterpart of the Goods Receipt: confirming marks units
``SOLD``, decrements accessory levels, and books ``SALE_REVENUE`` with its
``COGS`` against the same movement.

**A draft reserves no price**, which is why ``resolved_price`` and
``charged_price`` are nullable. A draft line carries an override if a
Manager typed one and nothing otherwise; both figures are written once, at
confirm, from a resolution that runs again at that moment (FR-4.5b1).
Freezing the scan-time price would charge a price the store has already
abandoned *and* write a deviation nobody made into FR-9.7's report.

What ``confirm`` checks here is only what lives on the aggregate.
Re-resolving a price needs the live unit and the live catalog row, so that
belongs to ``InvoicePoster`` — the same split ``GoodsReceipt`` keeps by
doing no I/O in its own ``confirm``.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.entities.document import Document
from domain.enums import TrackingType
from domain.errors import (
    CurrencyMismatchError,
    DuplicateScanError,
    EmptyInvoiceError,
    InvalidMoneyError,
)
from domain.value_objects import Currency, Money


@dataclass(eq=False, kw_only=True)
class SalesInvoiceLine(UuidEntity, TenantEntity):
    sales_invoice_id: UUID
    product_id: UUID
    # Set for a SERIAL line and None for a QUANTITY one: an accessory has
    # no per-unit identity to point at (§4.1).
    device_unit_id: UUID | None = None
    quantity: int = 1
    # The product's, carried onto the line by the repository's join.
    currency: Currency
    tracking_type: TrackingType
    # What a Manager typed for this one sale (FR-4.5). It survives
    # re-resolution at confirm and never reprices the unit in stock.
    override_price: Money | None = None
    # Stamped when the override is made, not at confirm: the person who
    # approves a discount and the person who confirms the invoice need not
    # be the same, and the ledger's user_id names the confirmer (FR-4.5f).
    price_approved_by: UUID | None = None
    price_note: str | None = None
    # Both written at confirm and never before (FR-4.5b, FR-4.5b1).
    resolved_price: Money | None = None
    charged_price: Money | None = None

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise InvalidMoneyError(f"a line for {self.quantity} units sells nothing")
        if self.tracking_type is TrackingType.SERIAL:
            if self.device_unit_id is None:
                raise InvalidMoneyError("a serialized line must name the handset it sells")
            if self.quantity != 1:
                raise InvalidMoneyError(
                    "a serialized line sells one named handset, so its quantity is 1"
                )
        elif self.device_unit_id is not None:
            raise InvalidMoneyError("a quantity line names no device unit (§4.1)")
        if self.price_approved_by is not None and self.override_price is None:
            raise InvalidMoneyError(
                "a line records who approved a price only where a price was overridden"
            )
        for label, amount in (
            ("override", self.override_price),
            ("resolved", self.resolved_price),
            ("charged", self.charged_price),
        ):
            self._assert_price(label, amount)

    @property
    def is_serial(self) -> bool:
        return self.tracking_type is TrackingType.SERIAL

    @property
    def line_total(self) -> Money | None:
        """What this line adds to the invoice, or None while it is a draft."""
        if self.charged_price is None:
            return None
        return self.charged_price * self.quantity

    @property
    def is_deviation(self) -> bool:
        """Charged something other than what the system resolved (FR-4.5f)."""
        if self.charged_price is None or self.resolved_price is None:
            return False
        return self.charged_price != self.resolved_price

    def override(self, price: Money | None, user_id: UUID, note: str | None = None) -> None:
        """Set or clear this line's price for this sale only (FR-4.5).

        Clearing hands the line back to resolution, which is not the same
        as pricing it at zero, so the approver and the note go with it.
        """
        self._assert_price("override", price)
        self.override_price = price
        self.price_approved_by = None if price is None else user_id
        self.price_note = None if price is None else note

    def snapshot(self, resolved: Money) -> None:
        """Fix what was resolved and what is charged, at confirm (FR-4.5b)."""
        self._assert_price("resolved", resolved)
        self.resolved_price = resolved
        self.charged_price = self.override_price if self.override_price is not None else resolved

    def _assert_price(self, label: str, amount: Money | None) -> None:
        if amount is None:
            return
        if amount.is_negative:
            raise InvalidMoneyError(
                f"a {label} price may not be negative — a giveaway is a zero-priced "
                "line, and money flowing the other way is a return (FR-4.5e)"
            )
        if amount.currency is not self.currency:
            raise CurrencyMismatchError(
                f"{label} price is {amount.currency.value} but the product is priced "
                f"in {self.currency.value} (§4.5 rule 3)"
            )


@dataclass(eq=False, kw_only=True)
class SalesInvoice(Document):
    location_id: UUID
    # Optional: a walk-in buying a case for cash is not a record the store
    # needs to keep (FR-4.1).
    customer_id: UUID | None = None
    lines: list[SalesInvoiceLine] = field(default_factory=list)

    def confirm(self, now: datetime, user_id: UUID) -> None:
        self.assert_editable()
        self._assert_has_lines()
        self._assert_no_unit_twice()
        super().confirm(now, user_id)

    def subtotals(self) -> dict[Currency, Money]:
        """One figure per currency present, never their sum (FR-2.7).

        Empty while the invoice is a draft, because a draft holds no prices.
        """
        totals: dict[Currency, Money] = {}
        for line in self.lines:
            total = line.line_total
            if total is None:
                continue
            running = totals.get(total.currency, Money.zero(total.currency))
            totals[total.currency] = running + total
        return totals

    def deviations(self) -> list[SalesInvoiceLine]:
        """The lines charged something other than the resolved price (FR-9.7)."""
        return [line for line in self.lines if line.is_deviation]

    def line_for_unit(self, device_unit_id: UUID) -> SalesInvoiceLine | None:
        """The line already selling this handset — FR-4.2's idempotent re-scan."""
        return next(
            (line for line in self.lines if line.device_unit_id == device_unit_id),
            None,
        )

    def line_for_product(self, product_id: UUID) -> SalesInvoiceLine | None:
        """The quantity line already holding *product_id*, if there is one."""
        return next(
            (line for line in self.lines if line.product_id == product_id and not line.is_serial),
            None,
        )

    def _assert_has_lines(self) -> None:
        if not self.lines:
            raise EmptyInvoiceError(f"{self.number} has no lines — nothing is being sold")

    def _assert_no_unit_twice(self) -> None:
        seen: set[UUID] = set()
        for line in self.lines:
            if line.device_unit_id is None:
                continue
            if line.device_unit_id in seen:
                raise DuplicateScanError(
                    f"{self.number} sells the same handset twice — one phone, one line"
                )
            seen.add(line.device_unit_id)
