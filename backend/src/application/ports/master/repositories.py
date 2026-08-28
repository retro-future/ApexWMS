"""MasterDB repository ports (PRD §3.1).

MasterDB is the tenant registry *and* the identity store: who a person is,
which platform roles they hold, which stores they may act in. What a person
may do inside one store is an ``Employee`` row — see ``ports/tenant/``.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from application.ports.repository import LegacyRepository
from domain.entities import (
    Invitation,
    RefreshTokenRecord,
    Tenant,
    User,
    UserAppRole,
    UserTenantAccess,
)


class TenantRepository(LegacyRepository[Tenant, UUID], Protocol):
    async def get_by_slug(self, slug: str) -> Tenant | None:
        """Resolve the handle an ``X-Tenant`` header names a tenant by."""
        ...

    async def list_all(self) -> list[Tenant]: ...


class UserRepository(LegacyRepository[User, UUID], Protocol):
    async def get_by_email(self, email: str) -> User | None:
        """Email is unique across the platform — one identity per person."""
        ...


class UserAppRoleRepository(LegacyRepository[UserAppRole, UUID], Protocol):
    async def list_for_user(self, user_id: UUID) -> list[UserAppRole]: ...


class UserTenantAccessRepository(LegacyRepository[UserTenantAccess, UUID], Protocol):
    async def list_for_user(self, user_id: UUID) -> list[UserTenantAccess]: ...

    async def exists(self, user_id: UUID, tenant_id: UUID) -> bool:
        """Whether an ``X-Tenant`` header naming this tenant may be trusted."""
        ...


class RefreshTokenRepository(LegacyRepository[RefreshTokenRecord, UUID], Protocol):
    async def revoke_all_for_user(self, user_id: UUID, now: datetime) -> None:
        """Revoke every live token for the user — the reuse-detection response."""
        ...


class InvitationRepository(LegacyRepository[Invitation, UUID], Protocol):
    """Plain CRUD — the parametrization alone pins the aggregate and DI key."""
