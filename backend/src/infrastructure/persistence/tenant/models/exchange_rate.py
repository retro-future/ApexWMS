import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantBase


class ExchangeRateModel(TenantBase):
    """What the store quoted, som per dollar, on one day (W9 B1).

    Append-only: re-quoting a day is another row, and the newest row for a
    day wins. Nothing points at "the current rate" as a column, because a
    sale points at the row it was struck against instead.

    ``Numeric`` rather than the minor-unit ``BigInteger`` the money columns
    use: a rate is not an amount, it has no currency exponent to inherit,
    and its scale is its own.
    """

    __tablename__ = "exchange_rates"
    __table_args__ = (
        Index("ix_exchange_rates_kind_day", "kind", "effective_on", "set_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    effective_on: Mapped[date] = mapped_column(Date())
    som_per_usd: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"))
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
