"""List a tenant's users with their roles (Owner-only endpoint)."""

from uuid import UUID

from application.dtos import UserWithRole
from application.ports import MembershipRepository


class ListUsers:
    def __init__(self, memberships: MembershipRepository) -> None:
        self._memberships = memberships

    async def execute(self, tenant_id: UUID) -> list[UserWithRole]:
        return await self._memberships.list_for_tenant(tenant_id)
