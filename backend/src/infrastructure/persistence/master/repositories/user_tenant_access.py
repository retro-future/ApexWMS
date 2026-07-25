from uuid import UUID

from sqlalchemy import select

from domain.entities import UserTenantAccess
from infrastructure.persistence.master.models import UserTenantAccessModel

from .base import MasterCrudRepository


class SqlUserTenantAccessRepository(
    MasterCrudRepository[UserTenantAccess, UUID, UserTenantAccessModel]
):
    model = UserTenantAccessModel

    def _key(self, grant: UserTenantAccess) -> UUID:
        return grant.id

    def _to_entity(self, row: UserTenantAccessModel) -> UserTenantAccess:
        return UserTenantAccess(id=row.id, user_id=row.user_id, tenant_id=row.tenant_id)

    def _to_model(self, grant: UserTenantAccess) -> UserTenantAccessModel:
        return UserTenantAccessModel(
            id=grant.id, user_id=grant.user_id, tenant_id=grant.tenant_id
        )

    def _apply(self, row: UserTenantAccessModel, grant: UserTenantAccess) -> None:
        row.tenant_id = grant.tenant_id

    async def list_for_user(self, user_id: UUID) -> list[UserTenantAccess]:
        rows = await self._session.scalars(
            select(UserTenantAccessModel).where(UserTenantAccessModel.user_id == user_id)
        )
        return [self._to_entity(r) for r in rows]

    async def exists(self, user_id: UUID, tenant_id: UUID) -> bool:
        found = await self._session.scalar(
            select(UserTenantAccessModel.id).where(
                UserTenantAccessModel.user_id == user_id,
                UserTenantAccessModel.tenant_id == tenant_id,
            )
        )
        return found is not None
