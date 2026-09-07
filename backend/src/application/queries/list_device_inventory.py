"""FR-9.1 at the unit level: browse every handset by IMEI, filterable.

The screen `/reports/stock-on-hand` answers "how many", this one answers "which
ones and where". ``daysInStock`` is only meaningful for a unit still on the
shelf; it is sent regardless and the caller decides whether to show it.
"""

from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.dtos import CurrentUser, DeviceInventoryStatusFilter
from application.models import DeviceInventoryRowData
from application.ports import Clock, DeviceUnitQueries
from application.sorting import DeviceInventorySort
from domain.enums import DeviceCondition
from domain.permissions import Permission


class ListDeviceInventoryQuery(PagedQuery[PagedResult[DeviceInventoryRowData]]):
    product_id: UUID | None = None
    product_search: str | None = None
    location_id: UUID | None = None
    condition: DeviceCondition | None = None
    status: DeviceInventoryStatusFilter | None = None
    sort: DeviceInventorySort = DeviceInventorySort.RECEIVED


class ListDeviceInventoryHandler(
    IRequestHandler[PagedResult[DeviceInventoryRowData], ListDeviceInventoryQuery]
):
    def __init__(
        self, units: DeviceUnitQueries, clock: Clock, current: CurrentUser
    ) -> None:
        self._units = units
        self._clock = clock
        self._current = current

    async def handle(
        self, request: ListDeviceInventoryQuery
    ) -> PagedResult[DeviceInventoryRowData]:
        rows, total = await self._units.list_inventory(
            page=request.page,
            page_size=request.page_size,
            product_id=request.product_id,
            product_search=request.product_search,
            location_id=request.location_id,
            condition=request.condition,
            status=request.status,
            sort=request.sort,
        )
        now = self._clock.now()
        show_cost = Permission.COST_VIEW in self._current.permissions
        return PagedResult[DeviceInventoryRowData].succeed_with_data(
            data=[
                DeviceInventoryRowData.from_entity(row, now, show_cost=show_cost)
                for row in rows
            ],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
