import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantBase


class FinancialTransactionModel(TenantBase):
    """The money ledger (PRD §4.6), written beside every stock movement
    that has a financial consequence — in the same transaction (FR-10.1).

    This table **does** carry its own ``currency``, unlike ``device_units``
    and the price logs. Those inherit a product's currency because they
    always belong to one; a transaction need not — ``PAYMENT_RECEIVED`` is
    a som payment against an invoice whose lines may be dollars (§4.7), and
    has no product at all. The currency is therefore a property of the
    entry, and every aggregate over this table groups by it.

    ``amount_minor`` is **signed**: the direction of §4.6 is the sign, not
    a second column. A reversal is the negation of what it reverses, so a
    cancelled document's category nets to zero by construction — where an
    amount and a separate direction can contradict each other.
    """

    __tablename__ = "financial_transactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    txn_type: Mapped[str] = mapped_column(String(30))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    document_type: Mapped[str] = mapped_column(String(30))
    document_id: Mapped[uuid.UUID] = mapped_column()
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id"), nullable=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id"), nullable=True
    )
    device_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("device_units.id"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
