"""FR-6.3: closing a count and reporting what it found.

The step §4.4's three-state lifecycle has no room for, and it earns its
place: closing freezes the count so that the three lists somebody reads —
matched, missing, unexpected — are the same three lists the confirm acts
on. Without it a phone scanned after the report was printed would be
adjusted for and never appear on it.

**Nothing is written to either ledger here.** A closed count is still a
draft: it has found discrepancies and applied none of them, which is
exactly the state an Owner or Manager needs in order to look at the report
before agreeing to it (FR-6.4). Reporting and applying are separate acts by
separate people, and this is the seam between them.

The response *is* the report. Every row carries its own outcome and the
three counts sit on the payload, so there is no separate report to fetch.
"""

from uuid import UUID

from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.models import StockCountData
from application.ports import Clock, StockCountRepository, TenantUnitOfWork
from application.services import DocumentLoader
from domain.permissions import Permission


class CloseStockCountCommand(Command[ResultWithData[StockCountData]]):
    # No body: this action needs nothing beyond the count in the URL.
    stock_count_id: UUID


class CloseStockCountHandler(
    IRequestHandler[ResultWithData[StockCountData], CloseStockCountCommand]
):
    def __init__(
        self,
        counts: StockCountRepository,
        loader: DocumentLoader,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._counts = counts
        self._loader = loader
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CloseStockCountCommand
    ) -> ResultWithData[StockCountData]:
        count = await self._loader.load_count(request.stock_count_id)

        count.close(self._clock.now(), self._current.user_id)
        await self._counts.update(count)
        await self._uow.commit()

        return ResultWithData[StockCountData].succeed_with_data(
            StockCountData.from_entity(
                count, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
