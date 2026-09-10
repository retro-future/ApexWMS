"""Owner updates tenant settings: the timezone (FR-10.8) and the letterhead (FR-8.1)."""

from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import Letterhead
from application.models import TenantSettingsData
from application.ports import TenantSettingsRepository, TenantUnitOfWork
from application.services import TimezoneValidator


class UpdateTenantSettingsCommand(Command[ResultWithData[TenantSettingsData]]):
    timezone: str
    business_name: str | None = None
    address: str | None = None
    runs_till: bool = False


class UpdateTenantSettingsHandler(
    IRequestHandler[ResultWithData[TenantSettingsData], UpdateTenantSettingsCommand]
):
    def __init__(
        self,
        settings: TenantSettingsRepository,
        uow: TenantUnitOfWork,
        timezones: TimezoneValidator,
    ) -> None:
        self._settings = settings
        self._uow = uow
        self._timezones = timezones

    async def handle(
        self, request: UpdateTenantSettingsCommand
    ) -> ResultWithData[TenantSettingsData]:
        self._timezones.validate(request.timezone)
        await self._settings.set_timezone(request.timezone)
        await self._settings.set_letterhead(
            Letterhead(business_name=request.business_name, address=request.address)
        )
        await self._settings.set_runs_till(request.runs_till)
        await self._uow.commit()
        # Read back rather than map what was just written: the logo is not
        # part of this command, and the response has to report whether one
        # is there.
        stored = await self._settings.get_letterhead()
        return ResultWithData[TenantSettingsData].succeed_with_data(
            TenantSettingsData.from_entity(request.timezone, stored, request.runs_till)
        )
