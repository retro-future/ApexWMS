"""Rename or deactivate a location. Never a delete — movements from M3
point here, and history is preserved (FR-2.4's rule, applied generally)."""

from uuid import UUID

from pydantic import Field

from application.core import Command, IRequestHandler, ResultWithData
from application.errors import DuplicateNameError, NotFoundError
from application.ports import LocationRepository, TenantUnitOfWork
from application.queries.get_location import LocationData


class UpdateLocationCommand(Command[ResultWithData[LocationData]]):
    name: str | None = None
    is_active: bool | None = None
    location_id: UUID | None = Field(default=None, exclude=True)


class UpdateLocationHandler(
    IRequestHandler[ResultWithData[LocationData], UpdateLocationCommand]
):
    def __init__(self, locations: LocationRepository, uow: TenantUnitOfWork) -> None:
        self._locations = locations
        self._uow = uow

    async def handle(self, request: UpdateLocationCommand) -> ResultWithData[LocationData]:
        assert request.location_id is not None
        location = await self._locations.get(request.location_id)
        if location is None:
            raise NotFoundError("no such location in this store")

        if request.name is not None:
            name = request.name.strip()
            owner = await self._locations.get_by_name(name)
            if owner is not None and owner.id != location.id:
                raise DuplicateNameError(f"a location called {name!r} already exists")
            location.name = name
        if request.is_active is not None:
            location.is_active = request.is_active

        await self._locations.update(location)
        await self._uow.commit()
        return ResultWithData[LocationData].succeed_with_data(
            LocationData.from_location(location)
        )
