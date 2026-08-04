"""Owner updates tenant settings (timezone for now — FR-10.8 depends on it)."""

from application.core import Command, IRequestHandler, ResultWithData
from application.models import TenantSettingsData
from application.ports import TenantSettingsRepository, TenantUnitOfWork
from application.services import TimezoneValidator


class UpdateTenantSettingsCommand(Command[ResultWithData[TenantSettingsData]]):
    timezone: str


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
        await self._uow.commit()
        return ResultWithData[TenantSettingsData].succeed_with_data(
            TenantSettingsData.from_entity(request.timezone)
        )
