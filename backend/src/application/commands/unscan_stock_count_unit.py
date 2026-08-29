"""Undoing a scan on an open count (§6, FR-6.3).

Two different acts behind one endpoint, and which one happens depends on
what the snapshot said:

- A handset the count **expected** goes back to *missing*. Its row stays,
  because the snapshot is history and deleting it would erase the fact that
  the books thought the phone was here.
- A handset nobody expected is **removed** outright. Its row exists only
  because somebody scanned it, so undoing the scan leaves nothing behind.

Draft and un-closed only: once the discrepancies have been reported, what
is applied has to be what was reported (FR-6.3).
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, Result
from application.errors import NotFoundError
from application.ports import TenantUnitOfWork
from application.specs import StockCountForWrite
from domain.entities import StockCount
from domain.value_objects import IMEI
from infrastructure.persistence.tenant.models import StockCountModel


class UnscanStockCountUnitCommand(Command[Result]):
    # No body: both values name what to undo and come straight off the URL.
    stock_count_id: UUID
    imei: str


class UnscanStockCountUnitHandler(IRequestHandler[Result, UnscanStockCountUnitCommand]):
    def __init__(
        self,
        counts: TenantDbRepository[StockCount, StockCountModel],
        uow: TenantUnitOfWork,
    ) -> None:
        self._counts = counts
        self._uow = uow

    async def handle(self, request: UnscanStockCountUnitCommand) -> Result:
        spec = StockCountForWrite(request.stock_count_id)
        count = await self._counts.find_one(spec)
        if count is None:
            raise NotFoundError(
                f"stock count {request.stock_count_id} does not exist in this store"
            )
        count.assert_countable()

        wanted = IMEI.parse(request.imei)
        row = count.unit_for_imei(wanted)
        if row is None or not row.scanned:
            raise NotFoundError(f"{count.number} has no scan of IMEI {wanted}")

        if row.expected:
            row.scanned = False
            await self._counts.update(count, spec)
            await self._uow.commit()
            return Result.succeed(f"{wanted} is missing again on {count.number}")

        count.units.remove(row)
        await self._counts.update(count, spec)
        await self._uow.commit()
        return Result.succeed(f"{wanted} removed from {count.number}")
