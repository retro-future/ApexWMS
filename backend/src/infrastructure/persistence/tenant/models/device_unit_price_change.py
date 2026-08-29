import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TenantBase
from .device_unit import DeviceUnitModel


class DeviceUnitPriceChangeModel(TenantBase):
    """One handset's markdown history (PRD §4.5b, FR-2.15).

    The same table shape as ``product_price_changes``, keyed on the unit
    instead of the model — same discipline, same reason, and the same
    ``verify-projections`` sweep. This introduces a table, not a concept.

    No currency column: the amounts inherit the product's currency through
    the unit that owns them (§4.5 rule 3), so a read joins
    ``device_units`` → ``products``.
    """

    __tablename__ = "device_unit_price_changes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    device_unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("device_units.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Null for the first pricing — at intake, or the first time anyone
    # priced a unit a stock count turned up (FR-6.4b).
    old_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    new_price_minor: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"))
    # viewonly: the amounts inherit the unit's product currency (§4.5 rule
    # 3), reached device_unit -> product; the log never writes either back.
    device_unit: Mapped[DeviceUnitModel] = relationship(lazy="raise", viewonly=True)
