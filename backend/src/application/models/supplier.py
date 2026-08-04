"""Response payload for one supplier.

No currency field anywhere on a supplier: currency belongs to the product
(PRD §4.5 rule 3), so the same supplier can invoice in both.
"""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from domain.entities import Supplier


class SupplierData(CamelModel):
    id: UUID
    name: str
    contact_name: str | None
    phone: str | None
    email: str | None
    is_active: bool

    @classmethod
    def from_entity(cls, supplier: Supplier) -> SupplierData:
        return cls(
            id=supplier.id,
            name=supplier.name,
            contact_name=supplier.contact_name,
            phone=supplier.phone,
            email=supplier.email,
            is_active=supplier.is_active,
        )
