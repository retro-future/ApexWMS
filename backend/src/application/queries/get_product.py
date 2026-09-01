"""Read one catalog entry."""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import ProductData
from domain.entities import Product
from infrastructure.persistence.tenant.models import ProductModel


class GetProductQuery(Query[ResultWithData[ProductData]]):
    product_id: UUID


class GetProductHandler(IRequestHandler[ResultWithData[ProductData], GetProductQuery]):
    def __init__(self, products: TenantDbRepository[Product, ProductModel]) -> None:
        self._products = products

    async def handle(self, request: GetProductQuery) -> ResultWithData[ProductData]:
        product = await self._products.get(request.product_id)
        if product is None:
            raise NotFoundError(
                "no such product in this store",
                key="not_found",
                subject_key="product",
            )
        return ResultWithData[ProductData].succeed_with_data(ProductData.from_entity(product))
