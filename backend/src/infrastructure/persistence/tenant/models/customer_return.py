import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import TenantBase
from .device_unit import DeviceUnitModel
from .product import ProductModel
from .sales_invoice import SalesInvoiceLineModel


class CustomerReturnModel(TenantBase):
    """Goods coming back from a customer (PRD §4.4, §5.4b).

    ``sales_invoice_id`` is not nullable: a return always unwinds part of a
    named sale, which is what gives each line a refund ceiling and a cost.

    ``debt_relief_minor`` carries no currency column because customer debt
    is always som (§4.7). It is deliberately not derived from the line
    refunds above it — those are in the products' own currencies and there
    is no rate to convert them with.
    """

    __tablename__ = "customer_returns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    sales_invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_invoices.id"), index=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True, index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id"), index=True
    )
    reason: Mapped[str] = mapped_column(String(30), index=True)
    debt_relief_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
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
    lines: Mapped[list[CustomerReturnLineModel]] = relationship(
        back_populates="customer_return",
        cascade="all, delete-orphan",
        lazy="raise",
        order_by="CustomerReturnLineModel.id",
    )


class CustomerReturnLineModel(TenantBase):
    """One handset or one count of an accessory coming back, and its refund.

    This line carries money where a ``supplier_return_lines`` row does not,
    and that is the difference between the two documents: goods go back to a
    supplier at their book value, but a customer is paid back at a price
    somebody agreed to. ``refund_price_minor`` is that agreement, capped at
    the invoice line's ``charged_price``.

    What the returned goods *cost* is still not here. It is replayed at
    confirm from the unit's own ``acquisition_cost`` or from the COGS the
    original sale booked, for the reason every other document keeps costs
    out of its lines (§4.6).
    """

    __tablename__ = "customer_return_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    customer_return_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_returns.id"), index=True
    )
    sales_invoice_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_invoice_lines.id"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    device_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("device_units.id"), nullable=True, index=True
    )
    # Counts goods, not money — the name deliberately does not end in _minor.
    quantity: Mapped[int] = mapped_column(Integer)
    refund_price_minor: Mapped[int] = mapped_column(BigInteger)
    refund_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    refund_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    customer_return: Mapped[CustomerReturnModel] = relationship(
        back_populates="lines", lazy="raise"
    )
    # viewonly: the line reads the product's currency and tracking type
    # (§4.5 rule 3), the handset's IMEI, and what the sale charged, and
    # writes none of them back.
    product: Mapped[ProductModel] = relationship(lazy="raise", viewonly=True)
    device_unit: Mapped[DeviceUnitModel | None] = relationship(
        lazy="raise", viewonly=True
    )
    sales_invoice_line: Mapped[SalesInvoiceLineModel] = relationship(
        lazy="raise", viewonly=True
    )
