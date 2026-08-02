import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import TenantBase


class StockLevelModel(TenantBase):
    """``(product, location) → quantity`` for QUANTITY products (§4.2).

    A **projection** of ``stock_movements``, never a source of truth: it is
    updated in the same transaction as the movement that causes it, and
    ``verify-projections`` recomputes it from the ledger and reports any
    disagreement.

    The unique constraint on the pair is what makes "the level" a
    well-defined thing. Without it two rows could describe the same
    product at the same location and the projection would have no single
    value to compare the ledger against.

    Serialized products have no row here — a phone's whereabouts is its own
    ``device_units.location_id``, the same projection at the grain its
    tracking type demands.
    """

    __tablename__ = "stock_levels"
    __table_args__ = (UniqueConstraint("product_id", "location_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    location_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("locations.id"))
    quantity: Mapped[int] = mapped_column(Integer)
