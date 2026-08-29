import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TenantBase
from .device_unit import DeviceUnitModel
from .product import ProductModel


class WriteOffModel(TenantBase):
    """Stock destroyed, lost or stolen (PRD §4.4, §5.6).

    The same columns as ``supplier_returns`` minus the supplier, and a
    different table rather than a flag on that one: a return is expected to
    produce a credit and a write-off is the store absorbing the cost, and
    §5.10 reads the two in different columns of the month-end report.
    """

    __tablename__ = "write_offs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"), index=True)
    # Mandatory (FR-6.5) and indexed: "how much did we lose to theft this
    # quarter" is the question this column exists to answer.
    reason: Mapped[str] = mapped_column(String(20), index=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Scanning adds and removes these while the write-off is a draft, so
    # the mapper syncs the collection on update. lazy="raise": a spec that
    # forgets to eager-load it fails at the query.
    lines: Mapped[list[WriteOffLineModel]] = relationship(
        back_populates="write_off",
        cascade="all, delete-orphan",
        lazy="raise",
        order_by="WriteOffLineModel.id",
    )


class WriteOffLineModel(TenantBase):
    """One handset or one count of an accessory being written off.

    No money column, for the reason ``supplier_return_lines`` has none: the
    loss is the goods' book value, and that is computed from the ledger at
    confirm rather than stored twice.
    """

    __tablename__ = "write_off_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    write_off_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("write_offs.id"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    device_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("device_units.id"), nullable=True, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)

    write_off: Mapped[WriteOffModel] = relationship(
        back_populates="lines", lazy="raise"
    )
    # viewonly: the line reads the product's currency and tracking type
    # (§4.5 rule 3) and the handset's IMEI, and writes neither back.
    product: Mapped[ProductModel] = relationship(lazy="raise", viewonly=True)
    device_unit: Mapped[DeviceUnitModel | None] = relationship(
        lazy="raise", viewonly=True
    )
