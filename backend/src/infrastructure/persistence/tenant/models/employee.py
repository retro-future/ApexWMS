import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantBase


class EmployeeModel(TenantBase):
    """A person's presence at this store.

    ``id`` is the master ``users.id``, not a fresh identifier — no foreign
    key can express that (different database), so it is a contract the
    architecture test enforces instead.
    """

    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # Copied from the master user so staff lists and, from M3, ledger joins
    # never need a cross-database read.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
