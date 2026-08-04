"""Every place this store keeps stock, oldest first — so the seeded
"Main Store" (PRD §3.4) is always the first row."""

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import LocationData
from application.ports import LocationRepository


class ListLocationsQuery(PagedQuery[PagedResult[LocationData]]):
    search: str | None = None
    is_active: bool | None = None


class ListLocationsHandler(IRequestHandler[PagedResult[LocationData], ListLocationsQuery]):
    def __init__(self, locations: LocationRepository) -> None:
        self._locations = locations

    async def handle(self, request: ListLocationsQuery) -> PagedResult[LocationData]:
        locations, total = await self._locations.list_page(
            page=request.page,
            page_size=request.page_size,
            search=request.search,
            is_active=request.is_active,
        )
        return PagedResult[LocationData].succeed_with_data(
            data=[LocationData.from_entity(loc) for loc in locations],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
