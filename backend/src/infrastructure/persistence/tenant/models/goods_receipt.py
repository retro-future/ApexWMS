import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TenantBase
from .product import ProductModel


class GoodsReceiptModel(TenantBase):
    """Goods arriving (PRD §4.4, FR-3.3b).

    ``supplier_id`` is nullable and ``acquisition_source`` says why: used
    stock arrives from walk-in customers, and that receipt names no
    supplier at all. ``customer_id`` is the walk-in it was bought from,
    when they were recorded.
    """

    __tablename__ = "goods_receipts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    acquisition_source: Mapped[str] = mapped_column(String(20), index=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("suppliers.id"), nullable=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True
    )
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=True, index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"))
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

    lines: Mapped[list[GoodsReceiptLineModel]] = relationship(
        back_populates="goods_receipt",
        cascade="all, delete-orphan",
        lazy="raise",
        order_by="GoodsReceiptLineModel.product_id, GoodsReceiptLineModel.id",
    )


class GoodsReceiptLineModel(TenantBase):
    """What is expected on this receipt, one product at a time.

    ``unit_cost_minor`` is nullable and belongs to QUANTITY lines only: a
    serialized line prices each handset individually (FR-3.4b), and it is
    also nullable because a Storekeeper opens the receipt while an Owner
    or Manager states the cost later (FR-3.12).
    """

    __tablename__ = "goods_receipt_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    goods_receipt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goods_receipts.id"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_cost_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    goods_receipt: Mapped[GoodsReceiptModel] = relationship(
        back_populates="lines", lazy="raise"
    )
    units: Mapped[list[ReceivedUnitModel]] = relationship(
        back_populates="line",
        cascade="all, delete-orphan",
        lazy="raise",
        order_by="ReceivedUnitModel.imei",
    )
    # viewonly: the line carries the product's currency and tracking type
    # for display (§4.5 rule 3), but never writes the product back.
    product: Mapped[ProductModel] = relationship(lazy="raise", viewonly=True)


class ReceivedUnitModel(TenantBase):
    """One scanned handset on an open receipt.

    Deliberately **not** ``device_units``. A scan is a line on a draft: it
    has no status, no location and no movement behind it, and the handset
    it describes does not exist in stock until the receipt is confirmed
    (§4.3 rule 1). Confirming is what turns each of these into a real unit.

    The unique constraint is per receipt line, not global — the same IMEI
    genuinely can appear on two receipts over a phone's life (received,
    returned, received again). Global uniqueness lives where it belongs,
    on ``device_units.imei``, and FR-3.5's scan-time check reads it.
    """

    __tablename__ = "goods_receipt_units"
    __table_args__ = (UniqueConstraint("goods_receipt_line_id", "imei"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    goods_receipt_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("goods_receipt_lines.id"), index=True
    )
    imei: Mapped[str] = mapped_column(String(15), index=True)
    imei2: Mapped[str | None] = mapped_column(String(15), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    condition: Mapped[str] = mapped_column(String(20))
    # Both nullable while the receipt is a draft; confirm refuses if either
    # is still missing where it is needed (FR-3.4b, FR-3.10).
    acquisition_cost_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    asking_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # The som handed to a walk-in against a USD booking (§4.5b). The one
    # place on this row where a second currency appears, and it enters no
    # total anywhere.
    cash_paid_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    cash_paid_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    line: Mapped[GoodsReceiptLineModel] = relationship(
        back_populates="units", lazy="raise"
    )


class DocumentSequenceModel(TenantBase):
    """The counter behind ``PO-2026-0001`` (§4.4).

    One row per (document type, year), handed out under a row lock so two
    operators opening a receipt in the same second cannot be given the
    same number.
    """

    __tablename__ = "document_sequences"

    document_type: Mapped[str] = mapped_column(String(30), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer)
