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

    def _to_model(self, user: User) -> UserModel:
        return UserModel(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            password_hash=user.password_hash,
            tenant_id=user.tenant_id,
            is_active=user.is_active,
            must_change_password=user.must_change_password,
            created_at=user.created_at,
        )

    def _apply(self, row: UserModel, user: User) -> None:
        row.email = user.email
        row.full_name = user.full_name
        row.password_hash = user.password_hash
        row.tenant_id = user.tenant_id
        row.is_active = user.is_active
        row.must_change_password = user.must_change_password

    async def get_by_email(self, email: str) -> User | None:
        return await self._find_one(UserModel.email == email)
