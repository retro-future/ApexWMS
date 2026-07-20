"""Singleton-row accessor — not aggregate CRUD, so no ``TenantCrudRepository``."""

from sqlalchemy import select

from infrastructure.persistence.tenant.models import TenantSettingsModel
from infrastructure.types import TenantSession

SETTINGS_ROW_ID = 1


class SqlTenantSettingsRepository:
    def __init__(self, session: TenantSession) -> None:
        self._session = session

    async def get_timezone(self) -> str:
        timezone = await self._session.scalar(
            select(TenantSettingsModel.timezone).where(
                TenantSettingsModel.id == SETTINGS_ROW_ID
            )
        )
        if timezone is None:
            raise LookupError("tenant_settings row missing — provisioning seed failed")
        return timezone

    async def set_timezone(self, timezone: str) -> None:
        row = await self._session.get(TenantSettingsModel, SETTINGS_ROW_ID)
        if row is None:
            raise LookupError("tenant_settings row missing — provisioning seed failed")
        row.timezone = timezone
