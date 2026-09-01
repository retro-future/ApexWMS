"""FR-6.4: applying a count's adjustments, and letting reality win.

The moment the books are made to agree with the shelf. Only an Owner or
Manager reaches here (§2.1), which is deliberate: the person who walked the
aisles reports what they found, and somebody else agrees to write off what
is missing.

The same shape as every other confirm — the aggregate decides whether the
count may be applied, ``CountPoster`` turns each discrepancy into rows, and
this handler owns the transaction both ledgers are written inside. The one
thing worth naming is what happens to a **surprise**: confirming creates
the ``DeviceUnit`` for a handset the store had no row for, with no asking
price, so FR-2.14 refuses to quote it at the counter until somebody prices
it (FR-6.4b).

Nothing is repaired quietly. A count that finds a phone missing books its
book value as a ``COUNT_ADJUSTMENT`` loss; there is no path that edits a
status or a level without a movement behind it (§4.3 rule 1).
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import StockCountData
from application.ports import Clock, TenantUnitOfWork
from application.services import CountPoster
from application.specs import StockCountForWrite
from domain.entities import StockCount
from domain.permissions import Permission
from infrastructure.persistence.tenant.models import StockCountModel


class ConfirmStockCountCommand(Command[ResultWithData[StockCountData]]):
    # No body: this action needs nothing beyond the count in the URL.
    stock_count_id: UUID


class ConfirmStockCountHandler(
    IRequestHandler[ResultWithData[StockCountData], ConfirmStockCountCommand]
):
    def __init__(
        self,
        counts: TenantDbRepository[StockCount, StockCountModel],
        poster: CountPoster,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._counts = counts
        self._poster = poster
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: ConfirmStockCountCommand
    ) -> ResultWithData[StockCountData]:
        spec = StockCountForWrite(request.stock_count_id)
        count = await self._counts.find_one(spec)
        if count is None:
            raise NotFoundError(
                f"stock count {request.stock_count_id} does not exist in this store",
                key="not_found",
                subject_key="stock_count",
            )

        count.confirm(self._clock.now(), self._current.user_id)
        await self._poster.apply(count)
        await self._counts.update(count, spec)
        await self._uow.commit()

        return ResultWithData[StockCountData].succeed_with_data(
            StockCountData.from_entity(
                count, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
