"""Read one location."""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import LocationData
from domain.entities import Location
from infrastructure.persistence.tenant.models import LocationModel


class GetLocationQuery(Query[ResultWithData[LocationData]]):
    location_id: UUID


class GetLocationHandler(IRequestHandler[ResultWithData[LocationData], GetLocationQuery]):
    def __init__(self, locations: TenantDbRepository[Location, LocationModel]) -> None:
        self._locations = locations

    async def handle(self, request: GetLocationQuery) -> ResultWithData[LocationData]:
        location = await self._locations.get(request.location_id)
        if location is None:
            raise NotFoundError("no such location in this store")
        return ResultWithData[LocationData].succeed_with_data(
            LocationData.from_entity(location)
        )
