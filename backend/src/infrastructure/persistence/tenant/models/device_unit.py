import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantBase


class DeviceUnitModel(TenantBase):
    """One physical handset (PRD §4.2).

    Not an ``ActivatableRow``: a phone does not get deactivated, it gets
    ``SOLD`` or ``WRITTEN_OFF``, and ``status`` says so with more
    precision than a boolean could. ``created_at`` is here anyway because
    the ageing report (FR-9.4) orders by how long a unit has sat.

    Money is three ``BIGINT`` columns and exactly one currency, which is
    **not** the unit's: ``acquisition_cost_minor`` and
    ``asking_price_minor`` inherit the product's (§4.5 rule 3), recovered
    by joining ``products``. ``cash_paid_currency`` is the sole exception,
    and it exists precisely because that amount is in a *different*
    currency from everything else on the row — a som figure beside a
    dollar booking (§4.5b). It joins no total anywhere.
    """

    __tablename__ = "device_units"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    imei: Mapped[str] = mapped_column(String(15), unique=True, index=True)
    imei2: Mapped[str | None] = mapped_column(String(15), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    status: Mapped[str] = mapped_column(String(30))
    # Null once the unit has left the store — sold, returned, written off.
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id"), nullable=True
    )
    acquisition_cost_minor: Mapped[int] = mapped_column(BigInteger)
    asking_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    condition: Mapped[str] = mapped_column(String(20))
    cash_paid_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cash_paid_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    # How the unit entered stock. Nullable because it need not have come
    # through a receipt: a stock count creates units for handsets the
    # system did not know it had (FR-6.4b). Not a foreign key — the six
    # document types live in six different tables.
    source_document_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
