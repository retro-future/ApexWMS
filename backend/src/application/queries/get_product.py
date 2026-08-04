"""Read one catalog entry."""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import ProductData
from application.ports import ProductRepository


class GetProductQuery(Query[ResultWithData[ProductData]]):
    product_id: UUID


class GetProductHandler(IRequestHandler[ResultWithData[ProductData], GetProductQuery]):
    def __init__(self, products: ProductRepository) -> None:
        self._products = products

    async def handle(self, request: GetProductQuery) -> ResultWithData[ProductData]:
        product = await self._products.get(request.product_id)
        if product is None:
            raise NotFoundError("no such product in this store")
        return ResultWithData[ProductData].succeed_with_data(ProductData.from_entity(product))
