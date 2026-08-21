from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantBase


class TenantSettingsModel(TenantBase):
    __tablename__ = "tenant_settings"

    # A single-row table; the row is created at provisioning with id=1.
    id: Mapped[int] = mapped_column(primary_key=True)
    timezone: Mapped[str] = mapped_column(String(64))
    # The letterhead a printed document carries (FR-8.1). Nullable
    # because provisioning cannot know either one.
    business_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
