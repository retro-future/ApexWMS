"""Response payload for a Sales Invoice — PRD §5.4, §8.

The nested line class lives here rather than in its own module: it is one
branch of this payload's tree, never returned on its own by anything.

**Every figure here is a price, not a cost** — with one deliberate
exception: ``belowCostAlerts`` on the confirm response carries the
accessory's average cost, shown to whoever confirmed the sale so a
below-cost sale is visible at the counter (see the below-cost design doc).
Nothing in this payload is behind ``Permission.Cost.View``. The margin on a
sale is a reporting question (FR-9.4, FR-10.5), answered from the ledgers by
someone who holds that permission, not a field on the document a Seller
reads.

A draft's money fields are all null, and that is the API telling the truth
about FR-4.5b1: a draft reserves no price. The figure the counter displays
while scanning comes from the scan response, which resolves a price to
*show* without writing one down.

The debt fields are the one place a som figure sits beside dollar line
prices, and they are unrelated to them by design (§4.7): the seller quotes
the som total in their head, and no rate is recorded anywhere.
``remainingMinor`` is computed on every read from
``debt − Σ payments − Σ return relief``,
which is also what makes it the refund figure once the invoice is
cancelled (FR-11.11) — the debt is void but the payments are not.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.dtos import BelowCostAlert
from application.models.below_cost_alert import BelowCostAlertData
from application.models.exchange_rate import ExchangeRateData
from application.models.money import MoneyData
from application.models.payment import PaymentData

# Imported from the module rather than the package: ``application.services``
# pulls in every poster, and several of those import this file.
from application.services.customer_balance import paid_on, relieved_on, remaining_on
from domain.entities import CustomerReturn, Payment, SalesInvoice, SalesInvoiceLine
from domain.enums import DocumentStatus, PaymentType, TrackingType
from domain.value_objects import Currency, Money


class SalesInvoiceLineData(CamelModel):
    id: UUID
    product_id: UUID
    device_unit_id: UUID | None
    quantity: int
    tracking_type: TrackingType
    currency: Currency
    # What the system resolved at confirm, and what was actually charged
    # (FR-4.5f). Both null while the invoice is a draft.
    resolved_price: MoneyData | None = None
    charged_price: MoneyData | None = None
    line_total: MoneyData | None = None
    # Set while the invoice is a draft too: an override is a decision
    # somebody made, not a figure the confirm produced.
    override_price: MoneyData | None = None
    price_approved_by: UUID | None = None
    price_note: str | None = None
    is_deviation: bool = False

    @classmethod
    def from_entity(cls, line: SalesInvoiceLine) -> SalesInvoiceLineData:
        return cls(
            id=line.id,
            product_id=line.product_id,
            device_unit_id=line.device_unit_id,
            quantity=line.quantity,
            tracking_type=line.tracking_type,
            currency=line.currency,
            resolved_price=MoneyData.from_entity(line.resolved_price),
            charged_price=MoneyData.from_entity(line.charged_price),
            line_total=MoneyData.from_entity(line.line_total),
            override_price=MoneyData.from_entity(line.override_price),
            price_approved_by=line.price_approved_by,
            price_note=line.price_note,
            is_deviation=line.is_deviation,
        )


class SalesInvoiceData(CamelModel):
    id: UUID
    number: str
    status: DocumentStatus
    location_id: UUID
    customer_id: UUID | None
    note: str | None
    created_by: UUID
    created_at: datetime
    confirmed_by: UUID | None
    confirmed_at: datetime | None
    cancelled_by: UUID | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    lines: list[SalesInvoiceLineData]
    # One figure per currency present, never their sum (FR-2.7). Empty on
    # a draft, because a draft holds no prices.
    subtotals: list[MoneyData]
    # How this sale is paid for (§4.7). All three debt figures are som.
    payment_type: PaymentType
    credit_company_id: UUID | None
    contract_ref: str | None
    debt: MoneyData | None = None
    paid: MoneyData
    # Som written off by confirmed customer returns (FR-4.9d).
    relieved: MoneyData
    remaining: MoneyData
    # What physically changed hands, one figure per currency — the till's
    # side of the sale, never netted against the revenue above it.
    tendered: list[MoneyData] = []
    payments: list[PaymentData] = []
    # The rate the store was quoting when this sale was confirmed (W9
    # B1). Populated only on the detail read, and null for a draft or a
    # sale confirmed before the rate log existed. Compare it against
    # ``tendered`` over ``subtotals`` to see the rate actually struck.
    sale_rate: ExchangeRateData | None = None
    # Populated only by the confirm handler (see the below-cost design doc);
    # empty on get/list/create/cancel.
    below_cost_alerts: list[BelowCostAlertData] = []

    @classmethod
    def from_entity(
        cls,
        invoice: SalesInvoice,
        payments: Sequence[Payment] = (),
        returns: Sequence[CustomerReturn] = (),
        *,
        below_cost_alerts: list[BelowCostAlert] | None = None,
        sale_rate: ExchangeRateData | None = None,
    ) -> SalesInvoiceData:
        # ``paid_on`` and not a plain sum: it counts only what settles the
        # som debt, so a tender in another currency cannot reduce it.
        paid = paid_on(payments)
        tendered: dict[Currency, Money] = {}
        for payment in payments:
            currency = payment.amount.currency
            tendered[currency] = (
                tendered.get(currency, Money.zero(currency)) + payment.amount
            )
        # Through ``remaining_on`` so the three-term balance is stated once
        # (§4.7, FR-4.9d) — a cancelled sale's debt is void, and any
        # payments taken are a refund, which is why they are still listed.
        owing = remaining_on(invoice, payments, returns)
        return cls(
            id=invoice.id,
            number=invoice.number,
            status=invoice.status,
            location_id=invoice.location_id,
            customer_id=invoice.customer_id,
            note=invoice.note,
            created_by=invoice.created_by,
            created_at=invoice.created_at,
            confirmed_by=invoice.confirmed_by,
            confirmed_at=invoice.confirmed_at,
            cancelled_by=invoice.cancelled_by,
            cancelled_at=invoice.cancelled_at,
            cancellation_reason=invoice.cancellation_reason,
            lines=[SalesInvoiceLineData.from_entity(line) for line in invoice.lines],
            subtotals=MoneyData.from_entity(invoice.subtotals()),
            payment_type=invoice.payment_type,
            credit_company_id=invoice.credit_company_id,
            contract_ref=invoice.contract_ref,
            debt=MoneyData.from_entity(invoice.debt),
            paid=MoneyData.from_entity(paid),
            relieved=MoneyData.from_entity(relieved_on(returns)),
            remaining=MoneyData.from_entity(owing),
            tendered=MoneyData.from_entity(tendered),
            payments=[PaymentData.from_entity(payment) for payment in payments],
            sale_rate=sale_rate,
            below_cost_alerts=[
                BelowCostAlertData.from_entity(one)
                for one in (below_cost_alerts or [])
            ],
        )
