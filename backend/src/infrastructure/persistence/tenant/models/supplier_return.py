import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TenantBase
from .device_unit import DeviceUnitModel
from .product import ProductModel


class SupplierReturnModel(TenantBase):
    """Goods going back to the supplier (PRD §4.4, §5.5).

    ``supplier_id`` is **not** nullable here, unlike on ``goods_receipts``.
    A trade-in arrives from a walk-in and so names no supplier, but nothing
    goes *back* to a walk-in: a used handset the store no longer wants is
    resold or written off.

    ``reason`` is a closed set (FR-5.1) so returns can be grouped by why;
    anything it does not capture goes in the shared ``note``.
    """

    __tablename__ = "supplier_returns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suppliers.id"), index=True)
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"), index=True)
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

    # Scanning adds and removes these while the return is a draft, so the
    # mapper syncs the collection on update. lazy="raise": a spec that
    # forgets to eager-load it fails at the query.
    lines: Mapped[list[SupplierReturnLineModel]] = relationship(
        back_populates="supplier_return",
        cascade="all, delete-orphan",
        lazy="raise",
        order_by="SupplierReturnLineModel.id",
    )


class SupplierReturnLineModel(TenantBase):
    """One handset or one count of an accessory going back.

    No money column anywhere: what the return is worth is the goods' book
    value, replayed at confirm from the unit's own cost or the weighted
    average pool (§4.6). Storing it here would be a second opinion about a
    figure the ledger already holds.
    """

    __tablename__ = "supplier_return_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    supplier_return_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supplier_returns.id"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    device_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("device_units.id"), nullable=True, index=True
    )
    # Counts goods, not money — the name deliberately does not end in _minor.
    quantity: Mapped[int] = mapped_column(Integer)

    supplier_return: Mapped[SupplierReturnModel] = relationship(
        back_populates="lines", lazy="raise"
    )
    # viewonly: the line reads the product's currency and tracking type
    # (§4.5 rule 3) and the handset's IMEI, and writes neither back.
    product: Mapped[ProductModel] = relationship(lazy="raise", viewonly=True)
    device_unit: Mapped[DeviceUnitModel | None] = relationship(
        lazy="raise", viewonly=True
    )
