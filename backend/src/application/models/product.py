"""Response payload for one catalog entry.

``ProductData`` is the single response payload for every product route —
get, list, create and update all return it, so the shape a client learns
once is the shape it always sees.

``currency`` stays alongside the price because it is the *product's* own
currency (FR-2.6) and a caller needs it while the product is still unpriced.
"""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from application.models.money import MoneyData
from domain.entities import Product
from domain.enums import TrackingType
from domain.value_objects import Currency


class ProductData(CamelModel):
    id: UUID
    sku: str
    name: str
    brand: str | None
    model: str | None
    tracking_type: TrackingType
    currency: Currency
    barcode: str | None
    default_sale_price: MoneyData | None
    is_active: bool

    @classmethod
    def from_entity(cls, product: Product) -> ProductData:
        return cls(
            id=product.id,
            sku=str(product.sku),
            name=product.name,
            brand=product.brand,
            model=product.model,
            tracking_type=product.tracking_type,
            currency=product.currency,
            barcode=str(product.barcode) if product.barcode else None,
            default_sale_price=MoneyData.from_entity(product.default_sale_price),
            is_active=product.is_active,
        )
