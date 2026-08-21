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
        letterhead = Letterhead(
            business_name=request.business_name, address=request.address
        )
        await self._settings.set_timezone(request.timezone)
        await self._settings.set_letterhead(letterhead)
        await self._uow.commit()
        return ResultWithData[TenantSettingsData].succeed_with_data(
            TenantSettingsData.from_entity(request.timezone, letterhead)
        )
