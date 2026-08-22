"""Response payload for one credit company.

No money fields, and there will not be any: the company pays the store in
full at sale time (PRD §4.7), so nothing is ever owed to or by it.
"""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from domain.entities import CreditCompany


class CreditCompanyData(CamelModel):
    id: UUID
    name: str
    contact_name: str | None
    phone: str | None
    email: str | None
    is_active: bool

    @classmethod
    def from_entity(cls, company: CreditCompany) -> CreditCompanyData:
        return cls(
            id=company.id,
            name=company.name,
            contact_name=company.contact_name,
            phone=company.phone,
            email=company.email,
            is_active=company.is_active,
        )
