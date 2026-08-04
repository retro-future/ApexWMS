"""Read tenant settings (TenantDB): the timezone, letterhead later (M7)."""

from application.core import IRequestHandler, Query, ResultWithData
from application.models import TenantSettingsData
from application.ports import TenantSettingsRepository


class GetTenantSettingsQuery(Query[ResultWithData[TenantSettingsData]]):
    pass


class GetTenantSettingsHandler(
    IRequestHandler[ResultWithData[TenantSettingsData], GetTenantSettingsQuery]
):
    def __init__(self, settings: TenantSettingsRepository) -> None:
        self._settings = settings

    async def handle(
        self, request: GetTenantSettingsQuery
    ) -> ResultWithData[TenantSettingsData]:
        timezone = await self._settings.get_timezone()
        return ResultWithData[TenantSettingsData].succeed_with_data(
            TenantSettingsData.from_entity(timezone)
        )
