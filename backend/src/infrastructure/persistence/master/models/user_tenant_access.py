import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import MasterBase


class UserTenantAccessModel(MasterBase):
    """Extra stores a user may act in, beyond ``users.tenant_id``."""

    __tablename__ = "user_tenant_access"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "tenant_id", name="uq_user_tenant_access_user_tenant"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
