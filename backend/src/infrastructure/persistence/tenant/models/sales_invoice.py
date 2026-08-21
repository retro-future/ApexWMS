import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantBase


class SalesInvoiceModel(TenantBase):
    """A sale to a customer (PRD §4.4, §5.4).

    Same shape as the other two documents: not a ``TenantActivatableRow``
    (a document is cancelled, not deactivated), and the actor columns are
    real foreign keys into ``employees``.

    ``customer_id`` is nullable because a walk-in buying a case for cash is
    not a record the store needs to keep (FR-4.1).
    """

    __tablename__ = "sales_invoices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id"), nullable=True, index=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class SalesInvoiceLineModel(TenantBase):
    """What is being sold, and for how much.

    The three money columns are three different facts and none of them is
    derivable from the others. ``override_price_minor`` is what a Manager
    typed while the invoice was a draft; ``resolved_price_minor`` and
    ``charged_price_minor`` are written once, at confirm, from a resolution
    that runs again at that moment (FR-4.5b1) — which is why both are
    nullable and stay null for the life of a draft. All three inherit the
    product's currency (§4.5 rule 3).

    ``price_approved_by`` is stamped when the override is made rather than
    at confirm, because the person who approves a discount and the person
    who confirms the invoice need not be the same (FR-4.5f).
    """

    __tablename__ = "sales_invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    sales_invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_invoices.id"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    device_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("device_units.id"), nullable=True, index=True
    )
    # Counts goods, not money — a plain INTEGER, and the name deliberately
    # does not end in _minor.
    quantity: Mapped[int] = mapped_column(Integer)
    override_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    price_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id"), nullable=True
    )
    price_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resolved_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    charged_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
