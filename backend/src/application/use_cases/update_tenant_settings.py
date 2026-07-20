"""Owner updates tenant settings (timezone for now — FR-10.8 depends on it)."""

from application.ports import TenantSettingsRepository, TenantUnitOfWork
from application.timezones import validate_timezone


class UpdateTenantSettings:
    def __init__(self, settings: TenantSettingsRepository, uow: TenantUnitOfWork) -> None:
        self._settings = settings
        self._uow = uow

    async def execute(self, timezone: str) -> str:
        validate_timezone(timezone)
        await self._settings.set_timezone(timezone)
        await self._uow.commit()
        return timezone
