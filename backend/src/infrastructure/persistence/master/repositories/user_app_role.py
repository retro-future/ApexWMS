from uuid import UUID

from sqlalchemy import select

from domain.entities import UserAppRole
from domain.roles import AppRole
from infrastructure.persistence.master.models import UserAppRoleModel

from .base import MasterCrudRepository


class SqlUserAppRoleRepository(MasterCrudRepository[UserAppRole, UUID, UserAppRoleModel]):
    model = UserAppRoleModel


    def _to_entity(self, row: UserAppRoleModel) -> UserAppRole:
        return UserAppRole(id=row.id, user_id=row.user_id, role=AppRole(row.role))

    def _to_model(self, entity: UserAppRole) -> UserAppRoleModel:
        return UserAppRoleModel(
            id=entity.id,
            user_id=entity.user_id,
            role=entity.role.value,
        )

    def _apply(self, row: UserAppRoleModel, entity: UserAppRole) -> None:
        row.role = entity.role.value

    async def list_for_user(self, user_id: UUID) -> list[UserAppRole]:
        return await self._find_many(
            select(UserAppRoleModel).where(UserAppRoleModel.user_id == user_id)
        )
