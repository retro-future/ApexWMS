"""FR-2.2: a Manager creates a location.

Names are unique within the store: provisioning already seeded one, and
two rows called "Warehouse" would make every movement's location column
ambiguous to the person reading a report.
"""

from uuid import uuid4

from application.core import Command, IRequestHandler, ResultWithData
from application.errors import DuplicateNameError
from application.models import LocationData
from application.ports import Clock, LocationRepository, TenantUnitOfWork
from domain.entities import Location


class CreateLocationCommand(Command[ResultWithData[LocationData]]):
    name: str


class CreateLocationHandler(
    IRequestHandler[ResultWithData[LocationData], CreateLocationCommand]
):
    def __init__(
        self, locations: LocationRepository, clock: Clock, uow: TenantUnitOfWork
    ) -> None:
        self._locations = locations
        self._clock = clock
        self._uow = uow

    async def handle(self, request: CreateLocationCommand) -> ResultWithData[LocationData]:
        name = request.name.strip()
        if await self._locations.get_by_name(name) is not None:
            raise DuplicateNameError(f"a location called {name!r} already exists")

        location = Location(
            id=uuid4(), name=name, is_active=True, created_at=self._clock.now()
        )
        await self._locations.add(location)
        await self._uow.commit()
        return ResultWithData[LocationData].succeed_with_data(
            LocationData.from_entity(location)
        )
