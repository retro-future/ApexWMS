import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import ActivatableRow, TenantBase


class SupplierModel(TenantBase, ActivatableRow):
    """Who this store buys from (PRD §4.2).

    No currency column — currency belongs to the product (§4.5 rule 3), so
    one supplier can invoice in both.
    """

    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
