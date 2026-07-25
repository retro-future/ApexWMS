import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import MasterBase


class UserAppRoleModel(MasterBase):
    """Identity's ``user_roles`` join, ported."""

    __tablename__ = "user_app_roles"
    # The surrogate primary key keeps this the same shape as every other
    # entity; this constraint is what stops a role being granted twice.
    __table_args__ = (
        UniqueConstraint("user_id", "role", name="uq_user_app_roles_user_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(50))
