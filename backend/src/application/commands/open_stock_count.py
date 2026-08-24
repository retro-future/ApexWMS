"""FR-6.1: a Storekeeper opens a count, and the system snapshots the shelf.

The one M6 command that does real work beyond the shared document shape.
Opening a count writes down **what the books expect right now**, in both
tracking types: one row per handset the ledger says is here, and one line
per accessory level. Everything after that is a comparison against that
frozen picture.

Snapshotting at open rather than computing at close is the whole design.
A count takes hours; sales and receipts keep happening while somebody walks
the aisles with a scanner. If the expected list were recomputed at close,
a phone sold *during* the count would show up as missing and the store
would book a loss on stock it had just been paid for.

The consequence, stated rather than discovered: goods that arrive after the
count opens are *unexpected* when scanned, and confirming brings them on a
second time. Counting a location that is actively receiving is a workflow
mistake, not a thing the system can fix — which is why the snapshot names
its moment in the document's ``created_at``.
"""

from uuid import UUID, uuid4

from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import StockCountData
from application.ports import (
    Clock,
    DeviceUnitRepository,
    LocationRepository,
    StockCountRepository,
    StockLevelRepository,
    TenantUnitOfWork,
)
from application.services import DocumentNumberer
from domain.entities import StockCount, StockCountLine, StockCountUnit
from domain.enums import DocumentStatus, DocumentType
from domain.permissions import Permission


class OpenStockCountCommand(Command[ResultWithData[StockCountData]]):
    location_id: UUID
    note: str | None = None


class OpenStockCountHandler(
    IRequestHandler[ResultWithData[StockCountData], OpenStockCountCommand]
):
    def __init__(
        self,
        counts: StockCountRepository,
        units: DeviceUnitRepository,
        levels: StockLevelRepository,
        locations: LocationRepository,
        numberer: DocumentNumberer,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._counts = counts
        self._units = units
        self._levels = levels
        self._locations = locations
        self._numberer = numberer
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: OpenStockCountCommand
    ) -> ResultWithData[StockCountData]:
        if await self._locations.get(request.location_id) is None:
            raise NotFoundError(
                f"location {request.location_id} does not exist in this store"
            )

        count = StockCount(
            id=uuid4(),
            number=await self._numberer.next(DocumentType.STOCK_COUNT),
            status=DocumentStatus.DRAFT,
            location_id=request.location_id,
            note=request.note,
            created_by=self._current.user_id,
            created_at=self._clock.now(),
        )
        count.units = await self._expected_units(count)
        count.lines = await self._expected_lines(count)

        await self._counts.add(count)
        await self._uow.commit()
        return self._result(count)

    async def _expected_units(self, count: StockCount) -> list[StockCountUnit]:
        """One row per handset the ledger says is at this location."""
        return [
            StockCountUnit(
                id=uuid4(),
                stock_count_id=count.id,
                imei=unit.imei,
                device_unit_id=unit.id,
                product_id=unit.product_id,
                expected=True,
                scanned=False,
            )
            for unit in await self._units.list_on_hand(count.location_id)
        ]

    async def _expected_lines(self, count: StockCount) -> list[StockCountLine]:
        """One line per accessory level, including the ones that are zero.

        A level of zero is still worth a line: "the books say none and we
        found three" is a discrepancy, and dropping the row would make it
        invisible until somebody scanned a barcode nobody expected.
        """
        return [
            StockCountLine(
                id=uuid4(),
                stock_count_id=count.id,
                product_id=level.product_id,
                expected_quantity=level.quantity,
            )
            for level in await self._levels.list_for_location(count.location_id)
        ]

    def _result(self, count: StockCount) -> ResultWithData[StockCountData]:
        return ResultWithData[StockCountData].succeed_with_data(
            StockCountData.from_entity(
                count, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
