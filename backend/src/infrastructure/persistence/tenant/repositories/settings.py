"""The singleton settings row seeded at provisioning.

One row, two accessors, no identity to look it up by — so ``TenantRepository``
rather than ``TenantCrudRepository``, which is what that base is for.
"""

from sqlalchemy import select

from infrastructure.persistence.tenant.models import TenantSettingsModel

from .base import TenantRepository

SETTINGS_ROW_ID = 1

# Not "no settings yet": provisioning seeds this row before the database is
# usable, so its absence means the tenant was never provisioned properly —
# worth naming rather than defaulting around.
_ROW_MISSING = "tenant_settings row missing — provisioning seed failed"


class SqlTenantSettingsRepository(TenantRepository):
    async def get_timezone(self) -> str:
        timezone = await self._session.scalar(
            select(TenantSettingsModel.timezone).where(
                TenantSettingsModel.id == SETTINGS_ROW_ID
            )
        )
        if timezone is None:
            raise LookupError(_ROW_MISSING)
        return timezone

    async def set_timezone(self, timezone: str) -> None:
        row = await self._row(TenantSettingsModel, SETTINGS_ROW_ID)
        if row is None:
            raise LookupError(_ROW_MISSING)
        row.timezone = timezone
