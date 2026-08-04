"""FR-9.2b: every catalog price a model has carried, with who and when.

Answers *"what was the shelf price of this model in March?"* — which no
individual invoice can. A confirmed invoice snapshots its own prices
(FR-4.5b) and so accounts for **that** sale, while saying nothing about
what the shelf price was during the twenty months nobody bought one.

The list is oldest-first and always begins with a null ``oldPrice``: that
first row is where the product's pricing started, not a gap in the data.
"""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import PriceChangeData
from application.ports import ProductPriceChangeRepository, ProductRepository


class GetProductPriceHistoryQuery(Query[ResultWithData[list[PriceChangeData]]]):
    product_id: UUID


class GetProductPriceHistoryHandler(
    IRequestHandler[ResultWithData[list[PriceChangeData]], GetProductPriceHistoryQuery]
):
    def __init__(
        self,
        products: ProductRepository,
        changes: ProductPriceChangeRepository,
    ) -> None:
        self._products = products
        self._changes = changes

    async def handle(
        self, request: GetProductPriceHistoryQuery
    ) -> ResultWithData[list[PriceChangeData]]:
        # An empty history and an unknown product are different answers,
        # and only the lookup can tell them apart.
        if await self._products.get(request.product_id) is None:
            raise NotFoundError("no such product in this store")

        changes = await self._changes.list_for_product(request.product_id)
        return ResultWithData[list[PriceChangeData]].succeed_with_data(
            [PriceChangeData.from_entity(change) for change in changes]
        )
