from uuid import UUID

from sqlalchemy import func, select

from application.dtos import UserWithRole
from domain.entities import Membership, MembershipKey
from domain.roles import Role
from infrastructure.persistence.master.models import MembershipModel, UserModel

from .base import MasterCrudRepository
from .user import user_entity


class SqlMembershipRepository(MasterCrudRepository[Membership, MembershipKey, MembershipModel]):
    model = MembershipModel

    def _key(self, membership: Membership) -> MembershipKey:
        return membership.key

    def _to_entity(self, row: MembershipModel) -> Membership:
        return Membership(user_id=row.user_id, tenant_id=row.tenant_id, role=Role(row.role))

    def _to_model(self, membership: Membership) -> MembershipModel:
        return MembershipModel(
            user_id=membership.user_id,
            tenant_id=membership.tenant_id,
            role=membership.role.value,
        )

    def _apply(self, row: MembershipModel, membership: Membership) -> None:
        row.role = membership.role.value

    async def list_for_user(self, user_id: UUID) -> list[Membership]:
        rows = await self._session.scalars(
            select(MembershipModel).where(MembershipModel.user_id == user_id)
        )
        return [self._to_entity(r) for r in rows]

    async def list_for_tenant(self, tenant_id: UUID) -> list[UserWithRole]:
        rows = await self._session.execute(
            select(UserModel, MembershipModel.role)
            .join(MembershipModel, MembershipModel.user_id == UserModel.id)
            .where(MembershipModel.tenant_id == tenant_id)
            .order_by(UserModel.created_at)
        )
        return [UserWithRole(user=user_entity(u), role=Role(role)) for u, role in rows]

    async def count_owners(self, tenant_id: UUID) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(MembershipModel)
            .where(
                MembershipModel.tenant_id == tenant_id,
                MembershipModel.role == Role.OWNER.value,
            )
        )
        return count or 0
