"""FR-6.2: writing down how many of an accessory are actually on the shelf.

The typed alternative to scanning each one. A shelf of two hundred screen
protectors is counted by eye and entered as a number; a shelf of six cases
is scanned. Both write the same field.

**Zero is a real answer and null is not the same as zero.** Entering 0 says
"I looked and there are none", which confirms a total loss; leaving the
line uncounted says nobody looked, and ``StockCount.confirm()`` adjusts
nothing for it. That is why this endpoint exists rather than defaulting an
uncounted line to zero at close.
"""

from uuid import UUID

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import StockCountData
from application.ports import StockCountRepository, TenantUnitOfWork
from application.services import DocumentLoader
from domain.permissions import Permission


class CountStockCountLineCommandPayload(CamelModel):
    # Counts goods, not money. Zero is meaningful; the aggregate refuses a
    # negative.
    counted_quantity: int


class CountStockCountLineCommand(
    CountStockCountLineCommandPayload, Command[ResultWithData[StockCountData]]
):
    # URL path segments, filled in by the router — never sent by the client.
    stock_count_id: UUID
    line_id: UUID


class CountStockCountLineHandler(
    IRequestHandler[ResultWithData[StockCountData], CountStockCountLineCommand]
):
    def __init__(
        self,
        counts: StockCountRepository,
        loader: DocumentLoader,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._counts = counts
        self._loader = loader
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CountStockCountLineCommand
    ) -> ResultWithData[StockCountData]:
        count = await self._loader.load_count(request.stock_count_id)
        count.assert_countable()

        line = next((ln for ln in count.lines if ln.id == request.line_id), None)
        if line is None:
            raise NotFoundError(f"{count.number} has no line {request.line_id}")

        line.counted_quantity = request.counted_quantity
        # Re-run the entity's invariants over the new figure: a negative
        # count must fail here rather than reach the row.
        line.__post_init__()

        await self._counts.update_line(line)
        await self._uow.commit()

        return ResultWithData[StockCountData].succeed_with_data(
            StockCountData.from_entity(
                count, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
