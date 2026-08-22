"""Response payload for one payment against store credit (PRD §4.7).

Every amount here is som, so ``amount`` and ``amountMinor`` are the same
number — UZS has exponent 0 (FR-2.9). Both are published anyway, because
every other money field on the API publishes both and a client that special-cases
one currency is a client that will get the other one wrong.

The amount is **signed**: a negative row is the compensating entry that
reverses an earlier payment (FR-11.8), and the original stays beside it.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from application.core import CamelModel
from domain.entities import Payment
from domain.enums import PaymentMethod


class PaymentData(CamelModel):
    id: UUID
    sales_invoice_id: UUID
    occurred_at: datetime
    amount: Decimal
    amount_minor: int
    method: PaymentMethod
    user_id: UUID
    note: str | None
    reverses_payment_id: UUID | None
    is_reversal: bool

    @classmethod
    def from_entity(cls, payment: Payment) -> PaymentData:
        return cls(
            id=payment.id,
            sales_invoice_id=payment.sales_invoice_id,
            occurred_at=payment.occurred_at,
            amount=payment.amount.as_major(),
            amount_minor=payment.amount.amount_minor,
            method=payment.method,
            user_id=payment.user_id,
            note=payment.note,
            reverses_payment_id=payment.reverses_payment_id,
            is_reversal=payment.is_reversal,
        )
