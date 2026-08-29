"""Which counts have been run, and which are still open."""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, PagedQuery, PagedResult
from application.dtos import CurrentUser
from application.models import StockCountData
from application.specs import StockCountBrowse
from domain.entities import StockCount
from domain.enums import DocumentStatus
from domain.permissions import Permission
from infrastructure.persistence.tenant.models import StockCountModel


class ListStockCountsQuery(PagedQuery[PagedResult[StockCountData]]):
    search: str | None = None
    status: DocumentStatus | None = None
    location_id: UUID | None = None


class ListStockCountsHandler(
    IRequestHandler[PagedResult[StockCountData], ListStockCountsQuery]
):
    def __init__(
        self,
        counts: TenantDbRepository[StockCount, StockCountModel],
        current: CurrentUser,
    ) -> None:
        self._counts = counts
        self._current = current

    async def handle(self, request: ListStockCountsQuery) -> PagedResult[StockCountData]:
        spec = StockCountBrowse(
            search=request.search,
            status=request.status,
            location_id=request.location_id,
        )
        total = await self._counts.count(spec)
        counts = await self._counts.find(spec.page(request.page, request.page_size))
        show_cost = Permission.COST_VIEW in self._current.permissions
        return PagedResult[StockCountData].succeed_with_data(
            data=[StockCountData.from_entity(c, show_cost=show_cost) for c in counts],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
