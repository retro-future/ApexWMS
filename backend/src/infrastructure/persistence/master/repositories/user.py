from uuid import UUID

from sqlalchemy import select

from domain.entities import User
from infrastructure.persistence.master.models import UserModel

from .base import MasterCrudRepository


def user_entity(row: UserModel) -> User:
    return User(
        id=row.id,
        email=row.email,
        full_name=row.full_name,
        password_hash=row.password_hash,
        is_active=row.is_active,
        created_at=row.created_at,
    )


class SqlUserRepository(MasterCrudRepository[User, UUID, UserModel]):
    model = UserModel

    def _key(self, user: User) -> UUID:
        return user.id

    def _to_entity(self, row: UserModel) -> User:
        return user_entity(row)

    def _to_model(self, user: User) -> UserModel:
        return UserModel(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            password_hash=user.password_hash,
            is_active=user.is_active,
            created_at=user.created_at,
        )

    def _apply(self, row: UserModel, user: User) -> None:
        row.email = user.email
        row.full_name = user.full_name
        row.password_hash = user.password_hash
        row.is_active = user.is_active

    async def get_by_email(self, email: str) -> User | None:
        row = await self._session.scalar(select(UserModel).where(UserModel.email == email))
        return user_entity(row) if row else None
