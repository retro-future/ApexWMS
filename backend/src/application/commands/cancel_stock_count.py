"""Cancelling a confirmed stock count (§4.4, FR-10.2).

**Compensation, never deletion.** Every ``COUNT_ADJUSTMENT`` the count
wrote gets its negation, and the handsets are reprojected from their own
timelines: a phone written off as missing comes back to ``IN_STOCK`` at the
location it was counted at.

**A surprise handset's row survives the cancellation**, and that is the
honest outcome rather than an oversight. ``LedgerPoster.reverse`` appends a
compensating ``-1``, which reprojects the unit to ``WRITTEN_OFF`` — the
store is no longer claiming to hold it, and its whole life is two movements
that net to zero. Deleting the row instead would destroy the record that
somebody once scanned that IMEI here, which is exactly the evidence §4.3
exists to keep.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import StockCountData
from application.ports import Clock, TenantUnitOfWork
from application.services import LedgerPoster
from application.specs import StockCountForWrite
from domain.entities import StockCount
from domain.enums import DocumentType
from domain.permissions import Permission
from infrastructure.persistence.tenant.models import StockCountModel


class CancelStockCountCommandPayload(CamelModel):
    reason: str | None = None


class CancelStockCountCommand(
    CancelStockCountCommandPayload, Command[ResultWithData[StockCountData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    stock_count_id: UUID


class CancelStockCountHandler(
    IRequestHandler[ResultWithData[StockCountData], CancelStockCountCommand]
):
    def __init__(
        self,
        counts: TenantDbRepository[StockCount, StockCountModel],
        poster: LedgerPoster,
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
        self, request: CancelStockCountCommand
    ) -> ResultWithData[StockCountData]:
        spec = StockCountForWrite(request.stock_count_id)
        count = await self._counts.find_one(spec)
        if count is None:
            raise NotFoundError(
                f"stock count {request.stock_count_id} does not exist in this store",
                key="not_found",
                subject_key="stock_count",
            )

        count.cancel(self._clock.now(), self._current.user_id, request.reason)
        await self._poster.reverse(DocumentType.STOCK_COUNT, count.id)
        await self._counts.update(count, spec)
        await self._uow.commit()

        return ResultWithData[StockCountData].succeed_with_data(
            StockCountData.from_entity(
                count, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
