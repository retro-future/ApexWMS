"""Which counts have been run, and which are still open."""

from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.dtos import CurrentUser
from application.models import StockCountData
from application.ports import StockCountRepository
from domain.enums import DocumentStatus
from domain.permissions import Permission


class ListStockCountsQuery(PagedQuery[PagedResult[StockCountData]]):
    search: str | None = None
    status: DocumentStatus | None = None
    location_id: UUID | None = None


class ListStockCountsHandler(
    IRequestHandler[PagedResult[StockCountData], ListStockCountsQuery]
):
    def __init__(self, counts: StockCountRepository, current: CurrentUser) -> None:
        self._counts = counts
        self._current = current

    async def handle(self, request: ListStockCountsQuery) -> PagedResult[StockCountData]:
        counts, total = await self._counts.list_page(
            page=request.page,
            page_size=request.page_size,
            search=request.search,
            status=request.status,
            location_id=request.location_id,
        )
        show_cost = Permission.COST_VIEW in self._current.permissions
        return PagedResult[StockCountData].succeed_with_data(
            data=[StockCountData.from_entity(c, show_cost=show_cost) for c in counts],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
