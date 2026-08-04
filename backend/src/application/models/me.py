"""Response payload for the authenticated user's own identity view (GET /auth/me)."""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from application.dtos import CurrentUser
from domain.entities import User
from domain.enums import AppRole, TenantRole


class MeData(CamelModel):
    user_id: UUID
    email: str
    full_name: str
    must_change_password: bool
    tenant_id: UUID | None = None
    role: TenantRole | None = None
    app_roles: list[AppRole] = []
    permissions: list[str] = []

    @classmethod
    def from_entity(cls, user: User, current: CurrentUser) -> MeData:
        return cls(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            must_change_password=user.must_change_password,
            tenant_id=current.tenant_id,
            role=current.tenant_role,
            app_roles=list(current.app_roles),
            permissions=sorted(current.permissions),
        )
