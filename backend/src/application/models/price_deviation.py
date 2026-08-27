"""One row of the price-deviations report — FR-9.7, PRD §5.9.

Every confirmed line charged something other than the price the system
resolved at confirm (FR-4.5f), in **both** directions: a handset sold above
its asking price is information too, so ``difference`` is signed and
nothing here takes an absolute value.

The report exists to make one pattern visible — *"one manager, one
customer, over and over"* — which is why the approver and the customer are
on every row, by name as well as by id, rather than left to be joined back
afterwards.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from application.core import CamelModel
from application.dtos import PriceDeviation
from domain.value_objects import Currency


class PriceDeviationData(CamelModel):
    invoice_id: UUID
    invoice_number: str
    confirmed_at: datetime
    customer_id: UUID | None
    customer_name: str | None
    product_id: UUID
    product_name: str
    # Null on an accessory line — there is no handset to name (§4.1).
    imei: str | None
    currency: Currency
    resolved_price: Decimal
    resolved_price_minor: int
    charged_price: Decimal
    charged_price_minor: int
    # Signed: negative is a discount, positive is a sale above the asking
    # price, and the report reports both.
    difference: Decimal
    difference_minor: int
    price_approved_by: UUID | None
    price_approved_by_name: str | None
    price_note: str | None

    @classmethod
    def from_entity(cls, deviation: PriceDeviation) -> PriceDeviationData:
        difference = deviation.difference
        return cls(
            invoice_id=deviation.invoice_id,
            invoice_number=deviation.invoice_number,
            confirmed_at=deviation.confirmed_at,
            customer_id=deviation.customer_id,
            customer_name=deviation.customer_name,
            product_id=deviation.product_id,
            product_name=deviation.product_name,
            imei=deviation.imei,
            currency=deviation.charged_price.currency,
            resolved_price=deviation.resolved_price.as_major(),
            resolved_price_minor=deviation.resolved_price.amount_minor,
            charged_price=deviation.charged_price.as_major(),
            charged_price_minor=deviation.charged_price.amount_minor,
            difference=difference.as_major(),
            difference_minor=difference.amount_minor,
            price_approved_by=deviation.price_approved_by,
            price_approved_by_name=deviation.price_approved_by_name,
            price_note=deviation.price_note,
        )
