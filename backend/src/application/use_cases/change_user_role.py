"""Owner changes a member's role, guarded against locking the tenant out."""

from uuid import UUID

from application.errors import LastOwnerError, NotFoundError
from application.ports import MasterUnitOfWork, MembershipRepository
from domain.entities import MembershipKey
from domain.roles import Role


class ChangeUserRole:
    def __init__(self, memberships: MembershipRepository, uow: MasterUnitOfWork) -> None:
        self._memberships = memberships
        self._uow = uow

    async def execute(self, tenant_id: UUID, target_user_id: UUID, new_role: Role) -> None:
        membership = await self._memberships.get(MembershipKey(target_user_id, tenant_id))
        if membership is None:
            raise NotFoundError("user is not a member of this tenant")
        if (
            membership.role is Role.OWNER
            and new_role is not Role.OWNER
            and await self._memberships.count_owners(tenant_id) <= 1
        ):
            raise LastOwnerError("a tenant must keep at least one Owner")
        membership.role = new_role
        await self._memberships.update(membership)
        await self._uow.commit()
