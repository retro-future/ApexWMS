import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantBase


class StockMovementModel(TenantBase):
    """The stock ledger (PRD §4.3) — the backbone of the system.

    Every row is immutable. Stock levels and device statuses are
    projections of this table, updated in the same transaction as the
    movement that causes them and never edited on their own.

    ``quantity_delta`` is a plain ``Integer``, not ``BigInteger``: it
    counts goods, not money. A single movement of two billion screen
    protectors is not a scenario, and the column deliberately does not end
    in ``_minor`` — the architecture test that forces money columns wide
    keys off exactly that suffix.

    ``document_id`` carries no foreign key because the six document types
    live in six different tables; ``document_type`` says which. ``user_id``
    does, and can only because ``Employee.id`` *is* the master ``User.id``
    (§3.1) — the reason identity was split the way it was.
    """

    __tablename__ = "stock_movements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    movement_type: Mapped[str] = mapped_column(String(30))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    # Set for a SERIAL line, null for a QUANTITY one — the two tracking
    # types write to the same ledger, and this column tells them apart.
    device_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("device_units.id"), nullable=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"))
    quantity_delta: Mapped[int] = mapped_column(Integer)
    document_type: Mapped[str] = mapped_column(String(30))
    document_id: Mapped[uuid.UUID] = mapped_column()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
