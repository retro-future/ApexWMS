"""The singleton settings row seeded at provisioning.

One row, no identity to look it up by, so this is a plain
``TenantSession``-backed class with its getters and setters written
directly rather than an aggregate repository.
"""

from sqlalchemy import select

from application.dtos import Letterhead, TenantLogo
from infrastructure.persistence.tenant.models import TenantSettingsModel
from infrastructure.types import TenantSession

SETTINGS_ROW_ID = 1

# Not "no settings yet": provisioning seeds this row before the database is
# usable, so its absence means the tenant was never provisioned properly —
# worth naming rather than defaulting around.
_ROW_MISSING = "tenant_settings row missing — provisioning seed failed"


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
            raise LookupError(_ROW_MISSING)
        return timezone

    async def set_timezone(self, timezone: str) -> None:
        (await self._row()).timezone = timezone

    async def get_letterhead(self) -> Letterhead:
        row = await self._row()
        logo = None
        if row.logo is not None and row.logo_content_type is not None:
            logo = TenantLogo(content=row.logo, content_type=row.logo_content_type)
        return Letterhead(
            business_name=row.business_name, address=row.address, logo=logo
        )

    async def set_letterhead(self, letterhead: Letterhead) -> None:
        row = await self._row()
        row.business_name = letterhead.business_name
        row.address = letterhead.address

    async def set_logo(self, logo: TenantLogo | None) -> None:
        row = await self._row()
        row.logo = None if logo is None else logo.content
        row.logo_content_type = None if logo is None else logo.content_type

    async def _row(self) -> TenantSettingsModel:
        row = await self._session.get(TenantSettingsModel, SETTINGS_ROW_ID)
        if row is None:
            raise LookupError(_ROW_MISSING)
        return row
