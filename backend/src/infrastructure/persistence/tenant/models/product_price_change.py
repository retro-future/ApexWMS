import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantBase


class ProductPriceChangeModel(TenantBase):
    """The catalog-price log (PRD §4.5b, FR-2.19).

    Not an ``ActivatableRow``: an append-only row is never deactivated and
    is ordered by when the change *happened*, not by when it was inserted,
    so it carries ``occurred_at`` instead of ``is_active``/``created_at``.

    There is no currency column. The amounts are bare minor units in the
    product's own currency (§4.5 rule 3), which is immutable once the
    product has history — so a join to ``products`` recovers it, and no
    row can drift out of step with the catalog entry it belongs to.

    ``user_id`` is a real foreign key into ``employees`` — the first place
    the "``Employee.id`` *is* the master ``User.id``" contract (§3.1) is
    load-bearing rather than notional.
    """

    __tablename__ = "product_price_changes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # Indexed as (product_id, occurred_at) by the migration, not here: the
    # log is only ever read as one product's history in time order.
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Null for the first pricing: it has no predecessor.
    old_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    new_price_minor: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id"))
