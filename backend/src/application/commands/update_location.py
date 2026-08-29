"""Rename or deactivate a location. Never a delete — movements from M3
point here, and history is preserved (FR-2.4's rule, applied generally)."""

from uuid import UUID

from pydantic import Field

from application.common.repository import TenantDbRepository
from application.common.specification import Specification
from application.core import Command, IRequestHandler, ResultWithData
from application.errors import DuplicateNameError, NotFoundError
from application.models import LocationData
from application.ports import TenantUnitOfWork
from application.specs import LocationForWrite
from domain.entities import Location
from infrastructure.persistence.tenant.models import LocationModel


class UpdateLocationCommand(Command[ResultWithData[LocationData]]):
    name: str | None = None
    is_active: bool | None = None
    location_id: UUID | None = Field(default=None, exclude=True)


class UpdateLocationHandler(
    IRequestHandler[ResultWithData[LocationData], UpdateLocationCommand]
):
    def __init__(
        self,
        locations: TenantDbRepository[Location, LocationModel],
        uow: TenantUnitOfWork,
    ) -> None:
        self._locations = locations
        self._uow = uow

    async def handle(self, request: UpdateLocationCommand) -> ResultWithData[LocationData]:
        assert request.location_id is not None
        location = await self._locations.find_one(LocationForWrite(request.location_id))
        if location is None:
            raise NotFoundError("no such location in this store")

        if request.name is not None:
            name = request.name.strip()
            taken = Specification(LocationModel).where(
                LocationModel.name == name, LocationModel.id != location.id
            )
            if await self._locations.exists(taken):
                raise DuplicateNameError(f"a location called {name!r} already exists")
            location.name = name
        if request.is_active is not None:
            location.is_active = request.is_active

        await self._locations.update(location)
        await self._uow.commit()
        return ResultWithData[LocationData].succeed_with_data(
            LocationData.from_entity(location)
        )
