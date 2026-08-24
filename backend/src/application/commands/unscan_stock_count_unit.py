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

from application.core import Command, IRequestHandler, Result
from application.errors import NotFoundError
from application.ports import StockCountRepository, TenantUnitOfWork
from application.services import DocumentLoader
from domain.value_objects import IMEI


class UnscanStockCountUnitCommand(Command[Result]):
    # No body: both values name what to undo and come straight off the URL.
    stock_count_id: UUID
    imei: str


class UnscanStockCountUnitHandler(IRequestHandler[Result, UnscanStockCountUnitCommand]):
    def __init__(
        self,
        counts: StockCountRepository,
        loader: DocumentLoader,
        uow: TenantUnitOfWork,
    ) -> None:
        self._counts = counts
        self._loader = loader
        self._uow = uow

    async def handle(self, request: UnscanStockCountUnitCommand) -> Result:
        count = await self._loader.load_count(request.stock_count_id)
        count.assert_countable()

        wanted = IMEI.parse(request.imei)
        row = count.unit_for_imei(wanted)
        if row is None or not row.scanned:
            raise NotFoundError(f"{count.number} has no scan of IMEI {wanted}")

        if row.expected:
            row.scanned = False
            await self._counts.update_unit(row)
            await self._uow.commit()
            return Result.succeed(f"{wanted} is missing again on {count.number}")

        count.units.remove(row)
        await self._counts.remove_unit(row.id)
        await self._uow.commit()
        return Result.succeed(f"{wanted} removed from {count.number}")
