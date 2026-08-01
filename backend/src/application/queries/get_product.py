"""Read one catalog entry.

``ProductData`` is the single response payload for every product route —
get, list, create and update all return it, so the shape a client learns
once is the shape it always sees.

The price is rendered twice on purpose: ``default_sale_price`` as an exact
major-unit ``Decimal`` (pydantic serializes it as a JSON *string*, so no
float ever appears on the wire), and ``default_sale_price_minor`` as the
integer actually stored. Neither is meaningful without ``currency`` —
USD and UZS do not share an exponent (PRD §4.5).
"""

from decimal import Decimal
from uuid import UUID

from application.core import CamelModel, IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.ports import ProductRepository
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
    default_sale_price: Decimal | None
    default_sale_price_minor: int | None
    is_active: bool

    @classmethod
    def from_product(cls, product: Product) -> ProductData:
        price = product.default_sale_price
        return cls(
            id=product.id,
            sku=str(product.sku),
            name=product.name,
            brand=product.brand,
            model=product.model,
            tracking_type=product.tracking_type,
            currency=product.currency,
            barcode=str(product.barcode) if product.barcode else None,
            default_sale_price=price.as_major() if price else None,
            default_sale_price_minor=price.amount_minor if price else None,
            is_active=product.is_active,
        )


class GetProductQuery(Query[ResultWithData[ProductData]]):
    product_id: UUID


class GetProductHandler(IRequestHandler[ResultWithData[ProductData], GetProductQuery]):
    def __init__(self, products: ProductRepository) -> None:
        self._products = products

    async def handle(self, request: GetProductQuery) -> ResultWithData[ProductData]:
        product = await self._products.get(request.product_id)
        if product is None:
            raise NotFoundError("no such product in this store")
        return ResultWithData[ProductData].succeed_with_data(ProductData.from_product(product))
