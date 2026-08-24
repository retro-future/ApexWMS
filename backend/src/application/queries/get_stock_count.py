"""One Stock Count — and FR-6.3's discrepancy report, which is the same thing.

There is no separate report endpoint. Every row carries its own outcome and
the three totals sit on the payload, so the same response answers "what
does this count say" while it is being scanned, after it is closed, and
after it has been applied.

A Storekeeper runs counts but may not see costs (§2.1), so the whole report
is readable without ``Permission.Cost.View`` — only a surprise handset's
stated cost is shaped out (FR-1.7).
"""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import CurrentUser
from application.models import StockCountData
from application.services import DocumentLoader
from domain.permissions import Permission


class GetStockCountQuery(Query[ResultWithData[StockCountData]]):
    stock_count_id: UUID


class GetStockCountHandler(
    IRequestHandler[ResultWithData[StockCountData], GetStockCountQuery]
):
    def __init__(self, loader: DocumentLoader, current: CurrentUser) -> None:
        self._loader = loader
        self._current = current

    async def handle(self, request: GetStockCountQuery) -> ResultWithData[StockCountData]:
        count = await self._loader.load_count(request.stock_count_id)
        return ResultWithData[StockCountData].succeed_with_data(
            StockCountData.from_entity(
                count, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
