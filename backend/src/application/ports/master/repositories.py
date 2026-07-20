"""MasterDB repository ports — one per aggregate (PRD §3.1).

Each extends ``Repository[EntityT, KeyT]``; only methods with no generic
shape are declared here.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from application.dtos import UserWithRole
from application.ports.repository import Repository
from domain.entities import (
    Invitation,
    Membership,
    MembershipKey,
    RefreshTokenRecord,
    Tenant,
    User,
)


class UserRepository(Repository[User, UUID], Protocol):
    async def get_by_email(self, email: str) -> User | None: ...


class TenantRepository(Repository[Tenant, UUID], Protocol):
    """Plain CRUD — the parametrization alone pins the aggregate and DI key."""


class MembershipRepository(Repository[Membership, MembershipKey], Protocol):
    async def list_for_user(self, user_id: UUID) -> list[Membership]: ...

    async def list_for_tenant(self, tenant_id: UUID) -> list[UserWithRole]: ...

    async def count_owners(self, tenant_id: UUID) -> int: ...


class RefreshTokenRepository(Repository[RefreshTokenRecord, UUID], Protocol):
    async def revoke_all_for_user(self, user_id: UUID, tenant_id: UUID, now: datetime) -> None:
        """Revoke every live token for the pair — the reuse-detection response."""
        ...


class InvitationRepository(Repository[Invitation, UUID], Protocol):
    """Plain CRUD — the parametrization alone pins the aggregate and DI key."""
