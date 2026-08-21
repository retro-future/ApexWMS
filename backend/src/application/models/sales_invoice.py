"""Response payload for a Sales Invoice — PRD §5.4, §8.

The nested line class lives here rather than in its own module: it is one
branch of this payload's tree, never returned on its own by anything.

**Every figure here is a price, and none of them is a cost.** A Seller must
see what they are charging, so nothing in this payload is behind
``Permission.Cost.View`` — and nothing needs to be, because what the goods
cost the store never appears on it (FR-1.7). The margin on a sale is a
reporting question (FR-9.4, FR-10.5), answered from the ledgers by someone
who holds that permission, not a field on the document a Seller reads.

A draft's money fields are all null, and that is the API telling the truth
about FR-4.5b1: a draft reserves no price. The figure the counter displays
while scanning comes from the scan response, which resolves a price to
*show* without writing one down.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from application.core import CamelModel
from application.models.currency_subtotal import CurrencySubtotalData
from domain.entities import SalesInvoice, SalesInvoiceLine
from domain.enums import DocumentStatus, TrackingType
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
    resolved_price: Decimal | None = None
    resolved_price_minor: int | None = None
    charged_price: Decimal | None = None
    charged_price_minor: int | None = None
    line_total: Decimal | None = None
    line_total_minor: int | None = None
    # Set while the invoice is a draft too: an override is a decision
    # somebody made, not a figure the confirm produced.
    override_price: Decimal | None = None
    override_price_minor: int | None = None
    price_approved_by: UUID | None = None
    price_note: str | None = None
    is_deviation: bool = False

    @staticmethod
    def _major(amount: Money | None) -> Decimal | None:
        return None if amount is None else amount.as_major()

    @staticmethod
    def _minor(amount: Money | None) -> int | None:
        return None if amount is None else amount.amount_minor

    @classmethod
    def from_entity(cls, line: SalesInvoiceLine) -> SalesInvoiceLineData:
        return cls(
            id=line.id,
            product_id=line.product_id,
            device_unit_id=line.device_unit_id,
            quantity=line.quantity,
            tracking_type=line.tracking_type,
            currency=line.currency,
            resolved_price=cls._major(line.resolved_price),
            resolved_price_minor=cls._minor(line.resolved_price),
            charged_price=cls._major(line.charged_price),
            charged_price_minor=cls._minor(line.charged_price),
            line_total=cls._major(line.line_total),
            line_total_minor=cls._minor(line.line_total),
            override_price=cls._major(line.override_price),
            override_price_minor=cls._minor(line.override_price),
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
    subtotals: list[CurrencySubtotalData]

    @classmethod
    def from_entity(cls, invoice: SalesInvoice) -> SalesInvoiceData:
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
            subtotals=CurrencySubtotalData.from_entity(invoice.subtotals()),
        )
