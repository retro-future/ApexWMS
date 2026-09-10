"""Response payload for one payment against store credit (PRD §4.7).

The amount is **signed**: a negative row is the compensating entry that
reverses an earlier payment (FR-11.8), and the original stays beside it.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.models.money import MoneyData
from domain.entities import Payment
from domain.enums import PaymentMethod


class PaymentData(CamelModel):
    id: UUID
    sales_invoice_id: UUID
    occurred_at: datetime
    amount: MoneyData
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
            amount=MoneyData.from_entity(payment.amount),
            method=payment.method,
            user_id=payment.user_id,
            note=payment.note,
            reverses_payment_id=payment.reverses_payment_id,
            is_reversal=payment.is_reversal,
        )
