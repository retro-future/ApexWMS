from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import ActivatableRow, TenantBase


class EmployeeModel(TenantBase, ActivatableRow):
    """A person's presence at this store.

    ``id`` is the master ``users.id``, not a fresh identifier — no foreign
    key can express that (different database), so it is a contract the
    architecture test enforces instead.
    """

    __tablename__ = "employees"

    # Copied from the master user so staff lists and, from M3, ledger joins
    # never need a cross-database read.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(50))
