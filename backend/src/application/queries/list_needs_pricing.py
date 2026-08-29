"""FR-9.6: everything in stock that cannot be sold for want of a price.

The residual path FR-3.10's intake guard cannot close. A receipt holding an
unpriced used handset will not confirm, but a stock count that finds an
IMEI nobody expected creates one anyway (FR-6.4b), and so does flipping a
priceless `NEW` unit to `USED` (FR-2.18). Both land here rather than at the
counter with a customer standing there.
"""

from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import NeedsPricingRowData
from application.ports import Clock, DeviceUnitQueries


class ListNeedsPricingQuery(PagedQuery[PagedResult[NeedsPricingRowData]]):
    location_id: UUID | None = None


class ListNeedsPricingHandler(
    IRequestHandler[PagedResult[NeedsPricingRowData], ListNeedsPricingQuery]
):
    def __init__(self, units: DeviceUnitQueries, clock: Clock) -> None:
        self._units = units
        self._clock = clock

    async def handle(
        self, request: ListNeedsPricingQuery
    ) -> PagedResult[NeedsPricingRowData]:
        rows, total = await self._units.list_needs_pricing(
            page=request.page,
            page_size=request.page_size,
            location_id=request.location_id,
        )
        now = self._clock.now()
        return PagedResult[NeedsPricingRowData].succeed_with_data(
            data=[NeedsPricingRowData.from_entity(row, now) for row in rows],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
