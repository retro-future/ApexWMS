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

The payment terms (§4.7) are the exception that proves the rule: which
payment type, which credit company, and what som debt the customer agreed
to are all facts about this invoice and nothing else, so they are checked
here. ``debt`` is a plain column and the *balance* is not: what is still
owed is ``debt − Σ payments``, derived every time it is asked for, because
a stored counter is a number that can drift away from the rows behind it.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.entities.document import Document
from domain.enums import PaymentType, TrackingType
from domain.errors import (
    AnonymousDebtError,
    CreditTermsError,
    CurrencyMismatchError,
    DuplicateScanError,
    EmptyInvoiceError,
    InvalidLineError,
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
            raise InvalidLineError(f"a line for {self.quantity} units sells nothing")
        if self.tracking_type is TrackingType.SERIAL:
            if self.device_unit_id is None:
                raise InvalidLineError("a serialized line must name the handset it sells")
            if self.quantity != 1:
                raise InvalidLineError(
                    "a serialized line sells one named handset, so its quantity is 1"
                )
        elif self.device_unit_id is not None:
            raise InvalidLineError("a quantity line names no device unit (§4.1)")
        if self.price_approved_by is not None and self.override_price is None:
            raise InvalidLineError(
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
    # How this sale is paid for (§4.7). A draft carries the seller's
    # intention; the confirm body states the terms that are actually struck.
    payment_type: PaymentType = PaymentType.PAID_IN_FULL
    credit_company_id: UUID | None = None
    contract_ref: str | None = None
    # Always som, whatever the lines are priced in, and never derived from
    # them: the seller writes the figure the customer agreed to pay (§4.7).
    debt: Money | None = None

    def __post_init__(self) -> None:
        self._assert_terms()

    def set_terms(
        self,
        payment_type: PaymentType,
        *,
        credit_company_id: UUID | None = None,
        contract_ref: str | None = None,
        debt: Money | None = None,
    ) -> None:
        """State how this sale is being paid for (FR-11.1). Draft only."""
        self.assert_editable()
        self.payment_type = payment_type
        self.credit_company_id = credit_company_id
        self.contract_ref = contract_ref
        self.debt = debt
        self._assert_terms()

    def confirm(self, now: datetime, user_id: UUID) -> None:
        self.assert_editable()
        self._assert_has_lines()
        self._assert_no_unit_twice()
        self._assert_terms()
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

    def _assert_terms(self) -> None:
        """Each payment type admits exactly one shape of terms (§4.7)."""
        if self.payment_type is PaymentType.STORE_CREDIT:
            self._assert_store_credit()
            return

        if self.debt is not None:
            raise CreditTermsError(
                f"{self.number} is {self.payment_type.value} and is settled at "
                "confirm, so it carries no debt (FR-11.4)"
            )
        if self.payment_type is PaymentType.CREDIT_COMPANY:
            if self.credit_company_id is None:
                raise CreditTermsError(
                    f"{self.number} is financed but names no credit company"
                )
            return

        if self.credit_company_id is not None or self.contract_ref is not None:
            raise CreditTermsError(
                f"{self.number} is paid in full and names a credit company"
            )

    def _assert_store_credit(self) -> None:
        if self.customer_id is None:
            raise AnonymousDebtError(
                f"{self.number} lends on store credit but names no customer — "
                "a debt has to belong to somebody (§4.7)"
            )
        if self.credit_company_id is not None:
            raise CreditTermsError(
                f"{self.number} is on the store's own book, so no credit company "
                "financed it"
            )
        if self.debt is None:
            raise CreditTermsError(
                f"{self.number} is on store credit but states no debt — the seller "
                "enters the total som the customer will pay (FR-11.5)"
            )
        if self.debt.currency is not Currency.UZS:
            raise CurrencyMismatchError(
                f"{self.number}'s debt is {self.debt.currency.value} but all "
                "customer debt is written in som (§4.7)"
            )
        if self.debt.is_zero or self.debt.is_negative:
            raise CreditTermsError(
                f"{self.number} owes {self.debt.format()} — a sale that opens no "
                "debt is paid in full"
            )
