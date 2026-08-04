"""Browse the catalog — the read half of the M2 demo.

Filtering and paging happen in the repository, not here: a handler that
fetched every product and sliced the list in Python would read the whole
catalog on every keystroke of a search box.
"""

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import ProductData
from application.ports import ProductRepository
from domain.enums import TrackingType


class ListProductsQuery(PagedQuery[PagedResult[ProductData]]):
    search: str | None = None
    is_active: bool | None = None
    tracking_type: TrackingType | None = None


class ListProductsHandler(
    IRequestHandler[PagedResult[ProductData], ListProductsQuery]
):
    def __init__(self, products: ProductRepository) -> None:
        self._products = products

    async def handle(self, request: ListProductsQuery) -> PagedResult[ProductData]:
        products, total = await self._products.list_page(
            page=request.page,
            page_size=request.page_size,
            search=request.search,
            is_active=request.is_active,
            tracking_type=request.tracking_type,
        )
        return PagedResult[ProductData].succeed_with_data(
            data=[ProductData.from_entity(p) for p in products],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
