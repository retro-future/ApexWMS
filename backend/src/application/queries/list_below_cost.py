"""FR-2.19 read backwards: active accessories whose weighted-average cost has
caught up to their catalog price, so every further sale books a loss until an
Owner or Manager reprices them. A worklist, not a block — selling below cost
can be deliberate.
"""

from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import BelowCostRowData
from application.ports import BelowCostQueries
from application.sorting import BelowCostSort


class ListBelowCostQuery(PagedQuery[PagedResult[BelowCostRowData]]):
    location_id: UUID | None = None
    sort: BelowCostSort = BelowCostSort.SHORTFALL


class ListBelowCostHandler(
    IRequestHandler[PagedResult[BelowCostRowData], ListBelowCostQuery]
):
    def __init__(self, below_cost: BelowCostQueries) -> None:
        self._below_cost = below_cost

    async def handle(
        self, request: ListBelowCostQuery
    ) -> PagedResult[BelowCostRowData]:
        rows, total = await self._below_cost.list_below_cost(
            page=request.page,
            page_size=request.page_size,
            location_id=request.location_id,
            sort=request.sort,
        )
        return PagedResult[BelowCostRowData].succeed_with_data(
            data=[BelowCostRowData.from_entity(row) for row in rows],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
