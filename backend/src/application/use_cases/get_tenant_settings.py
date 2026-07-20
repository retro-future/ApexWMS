"""Read tenant settings (TenantDB): the timezone, letterhead later (M7)."""

from application.ports import TenantSettingsRepository


class GetTenantSettings:
    def __init__(self, settings: TenantSettingsRepository) -> None:
        self._settings = settings

    async def execute(self) -> str:
        return await self._settings.get_timezone()
