"""Browse the catalog — the read half of the M2 demo.

Filtering and paging happen in the repository, not here: a handler that
fetched every product and sliced the list in Python would read the whole
catalog on every keystroke of a search box.
"""

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import ProductData
from application.specs import ProductBrowse
from domain.entities import Product
from domain.enums import TrackingType
from infrastructure.persistence.tenant.models import ProductModel


class ListProductsQuery(PagedQuery[PagedResult[ProductData]]):
    search: str | None = None
    is_active: bool | None = None
    tracking_type: TrackingType | None = None


class ListProductsHandler(
    IRequestHandler[PagedResult[ProductData], ListProductsQuery]
):
    def __init__(self, products: TenantDbRepository[Product, ProductModel]) -> None:
        self._products = products

    async def handle(self, request: ListProductsQuery) -> PagedResult[ProductData]:
        spec = ProductBrowse(
            search=request.search,
            is_active=request.is_active,
            tracking_type=request.tracking_type,
        )
        total = await self._products.count(spec)
        products = await self._products.find(spec.page(request.page, request.page_size))
        return PagedResult[ProductData].succeed_with_data(
            data=[ProductData.from_entity(p) for p in products],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
