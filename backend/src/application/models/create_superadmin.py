"""Response payload for seeding a platform operator. The temporary password
exists only here."""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from domain.entities import User


class CreateSuperAdminData(CamelModel):
    user_id: UUID
    email: str
    temporary_password: str

    @classmethod
    def from_entity(cls, user: User, temporary_password: str) -> CreateSuperAdminData:
        return cls(user_id=user.id, email=user.email, temporary_password=temporary_password)
