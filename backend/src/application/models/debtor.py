"""One line of the debtor list (FR-11.10).

The "who owes what" answer, and nothing more: no ageing buckets, no
overdue flag, no schedule. Store credit has no due date by design (PRD
§4.7), so there is nothing to be late against — ``daysSinceOldest`` is
what surfaces a debt that has been sitting for a year.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.dtos import DebtorSummary
from application.models.money import MoneyData


class DebtorData(CamelModel):
    customer_id: UUID
    full_name: str
    phone: str | None
    balance: MoneyData
    oldest_open_at: datetime
    days_since_oldest: int
    open_invoice_count: int

    @classmethod
    def from_entity(cls, debtor: DebtorSummary, now: datetime) -> DebtorData:
        return cls(
            customer_id=debtor.customer_id,
            full_name=debtor.full_name,
            phone=debtor.phone,
            balance=MoneyData.from_entity(debtor.balance),
            oldest_open_at=debtor.oldest_open_at,
            days_since_oldest=(now - debtor.oldest_open_at).days,
            open_invoice_count=debtor.open_invoice_count,
        )
