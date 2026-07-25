from uuid import UUID

from sqlalchemy import select

from domain.entities import UserAppRole
from domain.roles import AppRole
from infrastructure.persistence.master.models import UserAppRoleModel

from .base import MasterCrudRepository


class SqlUserAppRoleRepository(MasterCrudRepository[UserAppRole, UUID, UserAppRoleModel]):
    model = UserAppRoleModel

    def _key(self, assignment: UserAppRole) -> UUID:
        return assignment.id

    def _to_entity(self, row: UserAppRoleModel) -> UserAppRole:
        return UserAppRole(id=row.id, user_id=row.user_id, role=AppRole(row.role))

    def _to_model(self, assignment: UserAppRole) -> UserAppRoleModel:
        return UserAppRoleModel(
            id=assignment.id,
            user_id=assignment.user_id,
            role=assignment.role.value,
        )

    def _apply(self, row: UserAppRoleModel, assignment: UserAppRole) -> None:
        row.role = assignment.role.value

    async def list_for_user(self, user_id: UUID) -> list[UserAppRole]:
        rows = await self._session.scalars(
            select(UserAppRoleModel).where(UserAppRoleModel.user_id == user_id)
        )
        return [self._to_entity(r) for r in rows]
