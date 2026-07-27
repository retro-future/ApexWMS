from uuid import UUID

from domain.entities import User
from infrastructure.persistence.master.models import UserModel

from .base import MasterCrudRepository


class SqlUserRepository(MasterCrudRepository[User, UUID, UserModel]):
    model = UserModel


    def _to_entity(self, row: UserModel) -> User:
        return User(
            id=row.id,
            email=row.email,
            full_name=row.full_name,
            password_hash=row.password_hash,
            tenant_id=row.tenant_id,
            is_active=row.is_active,
            must_change_password=row.must_change_password,
            created_at=row.created_at,
        )

    def _to_model(self, entity: User) -> UserModel:
        return UserModel(
            id=entity.id,
            email=entity.email,
            full_name=entity.full_name,
            password_hash=entity.password_hash,
            tenant_id=entity.tenant_id,
            is_active=entity.is_active,
            must_change_password=entity.must_change_password,
            created_at=entity.created_at,
        )

    def _apply(self, row: UserModel, entity: User) -> None:
        row.email = entity.email
        row.full_name = entity.full_name
        row.password_hash = entity.password_hash
        row.tenant_id = entity.tenant_id
        row.is_active = entity.is_active
        row.must_change_password = entity.must_change_password

    async def get_by_email(self, email: str) -> User | None:
        return await self._find_one(UserModel.email == email)
