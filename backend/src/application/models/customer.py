"""Deliberately anemic (PRD §4.2). What a customer *owes* is not here: it is
derived from their invoices and payments (§4.7, M5b), so there is no
balance field that could drift from the ledger.
"""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from domain.entities import Customer


class CustomerData(CamelModel):
    id: UUID
    full_name: str
    phone: str | None
    is_active: bool

    @classmethod
    def from_entity(cls, customer: Customer) -> CustomerData:
        return cls(
            id=customer.id,
            full_name=customer.full_name,
            phone=customer.phone,
            is_active=customer.is_active,
        )
