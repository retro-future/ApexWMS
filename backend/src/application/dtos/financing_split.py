"""How the store actually sells — FR-10.5's last line.

One row per ``(payment type, credit company, currency)``: a credit-company
sale is only interesting broken down by company, and the other two payment
types have no company at all.
"""

from dataclasses import dataclass
from uuid import UUID

from domain.enums import PaymentType
from domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class FinancingSplitRow:
    payment_type: PaymentType
    credit_company_id: UUID | None
    credit_company_name: str | None
    invoice_count: int
    revenue: Money
