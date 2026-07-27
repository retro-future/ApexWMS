import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantBase


class CustomerModel(TenantBase):
    """Who this store sells to (PRD §4.2).

    ``full_name`` is indexed but *not* unique: two people share a name, and
    refusing the second at the till would be absurd. ``phone`` is indexed
    because that is what a seller actually has to search by.

    No balance column: what a customer owes is derived from their invoices
    and payments (§4.7), so there is nothing here to drift from the ledger.
    """

    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), index=True)
    phone: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
