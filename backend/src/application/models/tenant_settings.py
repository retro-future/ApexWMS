"""Response payload for tenant settings — the timezone, letterhead later (M7)."""

from __future__ import annotations

from application.core import CamelModel


class TenantSettingsData(CamelModel):
    timezone: str

    @classmethod
    def from_entity(cls, timezone: str) -> TenantSettingsData:
        return cls(timezone=timezone)
