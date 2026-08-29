"""FR-9.4: what has been sitting too long, and how hard it has been pushed.

``days`` is turned into an instant here rather than in the repository, so
the clock stays in one place and the statement behind this is reproducible.
"""

from datetime import timedelta
from uuid import UUID

from pydantic import Field

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.dtos import CurrentUser
from application.models import AgeingRowData
from application.ports import Clock, DeviceUnitQueries
from application.sorting import AgeingSort
from domain.permissions import Permission


class ListAgeingQuery(PagedQuery[PagedResult[AgeingRowData]]):
    days: int = Field(default=30, ge=0)
    location_id: UUID | None = None
    sort: AgeingSort = AgeingSort.AGE


class ListAgeingHandler(IRequestHandler[PagedResult[AgeingRowData], ListAgeingQuery]):
    def __init__(
        self, units: DeviceUnitQueries, clock: Clock, current: CurrentUser
    ) -> None:
        self._units = units
        self._clock = clock
        self._current = current

    async def handle(self, request: ListAgeingQuery) -> PagedResult[AgeingRowData]:
        now = self._clock.now()
        rows, total = await self._units.list_ageing(
            page=request.page,
            page_size=request.page_size,
            received_before=now - timedelta(days=request.days),
            location_id=request.location_id,
            sort=request.sort,
        )
        show_cost = Permission.COST_VIEW in self._current.permissions
        return PagedResult[AgeingRowData].succeed_with_data(
            data=[
                AgeingRowData.from_entity(row, now, show_cost=show_cost) for row in rows
            ],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
