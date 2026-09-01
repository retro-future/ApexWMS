"""One stock count, and FR-6.3's discrepancy report, which is the same thing.

There is no separate report endpoint. Every row carries its own outcome and
the three totals sit on the payload, so one response answers "what does
this count say" while it is being scanned, after it is closed, and after it
has been applied.

A Storekeeper runs counts but may not see costs (PRD 2.1), so the whole
report is readable without Permission.COST_VIEW; only a surprise handset's
stated cost is shaped out (FR-1.7).
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import StockCountData
from application.specs import StockCountById
from domain.entities import StockCount
from domain.permissions import Permission
from infrastructure.persistence.tenant.models import StockCountModel


class GetStockCountQuery(Query[ResultWithData[StockCountData]]):
    stock_count_id: UUID


class GetStockCountHandler(
    IRequestHandler[ResultWithData[StockCountData], GetStockCountQuery]
):
    def __init__(
        self,
        counts: TenantDbRepository[StockCount, StockCountModel],
        current: CurrentUser,
    ) -> None:
        self._counts = counts
        self._current = current

    async def handle(self, request: GetStockCountQuery) -> ResultWithData[StockCountData]:
        count = await self._counts.find_one(StockCountById(request.stock_count_id))
        if count is None:
            raise NotFoundError(
                f"stock count {request.stock_count_id} does not exist in this store",
                key="not_found",
                subject_key="stock_count",
            )
        return ResultWithData[StockCountData].succeed_with_data(
            StockCountData.from_entity(
                count, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
