import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantBase


class PaymentModel(TenantBase):
    """Money received against a store-credit sale (PRD §4.7, FR-11.6).

    Append-only, like both ledgers: rows are never updated or deleted, and
    a mistaken payment is compensated by a negative one naming it through
    ``reverses_payment_id``. That column is unique, which is what stops a
    payment being reversed twice.

    Carries its own currency because two different things land here: money
    against a store-credit debt, which is always som (§4.7), and what was
    physically handed over on a sale settled at confirm, which is in
    whatever currency the customer paid.
    """

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    sales_invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_invoices.id"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    # Signed: the direction is the sign, as it is in the money ledger.
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    method: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reverses_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payments.id"), nullable=True, unique=True
    )
