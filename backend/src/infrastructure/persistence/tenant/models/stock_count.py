import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TenantBase
from .product import ProductModel


class StockCountModel(TenantBase):
    """A physical count of one location (PRD §4.4, §5.6).

    ``closed_by``/``closed_at`` are the fourth step the shared
    ``DocumentStatus`` deliberately has no value for: open, scan, close,
    confirm. Only a count has a close, and adding a shared enum member
    would give every Purchase Order a state it can never enter. Closing is
    what freezes the discrepancy report so that what was reported and what
    gets applied describe the same shelf (FR-6.3).
    """

    __tablename__ = "stock_counts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"), index=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    # Scanning and counting change these while the count is open, so the
    # mapper syncs both collections. lazy="raise": a spec that forgets to
    # eager-load fails at the query.
    units: Mapped[list[StockCountUnitModel]] = relationship(
        back_populates="stock_count",
        cascade="all, delete-orphan",
        lazy="raise",
        order_by="StockCountUnitModel.imei",
    )
    lines: Mapped[list[StockCountLineModel]] = relationship(
        back_populates="stock_count",
        cascade="all, delete-orphan",
        lazy="raise",
        order_by="StockCountLineModel.product_id",
    )


class StockCountUnitModel(TenantBase):
    """One handset the count knows about, from either direction (FR-6.3).

    A row exists because the opening snapshot expected the handset, or
    because somebody scanned it, or both — and which of those is true is
    the entire discrepancy report. Storing the three lists as two booleans
    rather than one outcome column is what keeps *matched* from having to
    be written twice: the scan sets ``scanned`` on a row the snapshot
    already wrote.

    ``device_unit_id`` and ``product_id`` are null together, for a scan of
    an IMEI the store has no row for at all. ``acquisition_cost_minor`` is
    null for every other row: an expected handset already carries its own
    cost, and only a genuine surprise needs one stated (FR-6.4b). It
    inherits the product's currency, like every other unit amount
    (§4.5 rule 3), which is why there is no currency column.

    The unique constraint is per count, not global: the same IMEI is
    legitimately counted in January and again in February.
    """

    __tablename__ = "stock_count_units"
    __table_args__ = (UniqueConstraint("stock_count_id", "imei"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stock_count_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stock_counts.id"), index=True
    )
    imei: Mapped[str] = mapped_column(String(15), index=True)
    device_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("device_units.id"), nullable=True, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id"), nullable=True
    )
    expected: Mapped[bool] = mapped_column(Boolean)
    scanned: Mapped[bool] = mapped_column(Boolean)
    acquisition_cost_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    stock_count: Mapped[StockCountModel] = relationship(
        back_populates="units", lazy="raise"
    )
    # viewonly and nullable: a surprise IMEI names no product until somebody
    # says which model it is, and the unit only reads the currency back.
    product: Mapped[ProductModel | None] = relationship(lazy="raise", viewonly=True)


class StockCountLineModel(TenantBase):
    """One accessory the count expects a number of (FR-6.2).

    ``counted_quantity`` is nullable because a shelf nobody looked at and a
    shelf found empty are different findings: confirming the first would
    book a loss on evidence that does not exist.
    """

    __tablename__ = "stock_count_lines"
    __table_args__ = (UniqueConstraint("stock_count_id", "product_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stock_count_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stock_counts.id"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    # Both count goods, not money — neither name ends in _minor.
    expected_quantity: Mapped[int] = mapped_column(Integer)
    counted_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    stock_count: Mapped[StockCountModel] = relationship(
        back_populates="lines", lazy="raise"
    )
