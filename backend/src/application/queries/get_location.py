"""Read one location (PRD §4.2: a store, a stockroom, a warehouse)."""

from uuid import UUID

from application.core import CamelModel, IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.ports import LocationRepository
from domain.entities import Location


class LocationData(CamelModel):
    id: UUID
    name: str
    is_active: bool

    @classmethod
    def from_location(cls, location: Location) -> LocationData:
        return cls(id=location.id, name=location.name, is_active=location.is_active)


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
            LocationData.from_location(location)
        )
