import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantBase


class PurchaseOrderModel(TenantBase):
    """An intention to buy (PRD §4.4, FR-3.1).

    Not a ``TenantActivatableRow``: a document is cancelled, not
    deactivated, and ``status`` carries three states a boolean cannot.

    The three actor columns are foreign keys into ``employees`` for the
    same reason the ledgers' ``user_id`` is (§3.1): ``Employee.id`` *is*
    the master ``User.id``, so who raised, confirmed or called off a
    document is a real reference rather than a loose UUID.
    """

    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("suppliers.id"))
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


class PurchaseOrderLineModel(TenantBase):
    """What was ordered, at what price.

    ``unit_cost_minor`` inherits the product's currency (§4.5 rule 3), so
    an order for a USD phone and a UZS case holds two currencies and no
    column anywhere for their sum. It is nullable: a line may be raised
    before a price is agreed with the supplier, and ``PurchaseOrder.confirm()``
    refuses to confirm while one is still missing (FR-3.1).
    """

    __tablename__ = "purchase_order_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_orders.id"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    # Counts goods, not money — a plain INTEGER, and the name deliberately
    # does not end in _minor.
    quantity: Mapped[int] = mapped_column(Integer)
    unit_cost_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
