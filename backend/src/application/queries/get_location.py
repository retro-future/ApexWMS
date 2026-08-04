"""Read one location."""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import LocationData
from application.ports import LocationRepository


class GetLocationQuery(Query[ResultWithData[LocationData]]):
    location_id: UUID


class GetLocationHandler(IRequestHandler[ResultWithData[LocationData], GetLocationQuery]):
    def __init__(self, locations: LocationRepository) -> None:
        self._locations = locations

    async def handle(self, request: GetLocationQuery) -> ResultWithData[LocationData]:
        location = await self._locations.get(request.location_id)
        if location is None:
            raise NotFoundError("no such location in this store")
        return ResultWithData[LocationData].succeed_with_data(
            LocationData.from_entity(location)
        )
