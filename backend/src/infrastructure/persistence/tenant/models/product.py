from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import ActivatableRow, TenantBase


class ProductModel(TenantBase, ActivatableRow):
    """A catalog entry (PRD §4.2).

    One ``currency`` column, not one per amount: currency is a property of
    the product (§4.5 rule 3) and every amount downstream inherits it, so
    ``default_sale_price_minor`` is a bare integer that is only meaningful
    alongside it.

    ``BigInteger`` is mandatory, not defensive: a mid-range phone is about
    12 000 000 so'm and a 32-bit integer overflows at roughly 175 of them
    (§11).
    """

    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tracking_type: Mapped[str] = mapped_column(String(20))
    currency: Mapped[str] = mapped_column(String(3))
    # Unique, but nullable: Postgres treats NULLs as distinct, so every
    # SERIAL product can carry no barcode without colliding (FR-2.3).
    barcode: Mapped[str | None] = mapped_column(String(20), unique=True, index=True, nullable=True)
    default_sale_price_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
