"""Response payload for creating a store and its Owner. The temporary
password exists only here — it is never stored in plaintext."""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from domain.entities import Tenant, User


class CreateTenantData(CamelModel):
    tenant_id: UUID
    slug: str
    owner_email: str
    owner_user_id: UUID
    temporary_password: str

    @classmethod
    def from_entity(cls, tenant: Tenant, owner: User, temporary_password: str) -> CreateTenantData:
        return cls(
            tenant_id=tenant.id,
            slug=tenant.slug,
            owner_email=owner.email,
            owner_user_id=owner.id,
            temporary_password=temporary_password,
        )
