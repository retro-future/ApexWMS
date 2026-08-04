"""Response payload for a successful login."""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from application.dtos import AuthTokens, IssuedClaims
from domain.entities import User
from domain.enums import AppRole, TenantRole


class LoginData(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    # None for a platform operator, whose token carries no tenant claim.
    tenant_id: UUID | None = None
    role: TenantRole | None = None
    app_roles: list[AppRole] = []
    # True for someone still on a provisioned temporary password.
    must_change_password: bool = False

    @classmethod
    def from_entity(cls, tokens: AuthTokens, user: User, claims: IssuedClaims) -> LoginData:
        return cls(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            must_change_password=user.must_change_password,
            tenant_id=claims.tenant_id,
            role=claims.tenant_role,
            app_roles=list(claims.app_roles),
        )
