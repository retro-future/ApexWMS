"""Response payload for tenant settings — the timezone and the letterhead."""

from __future__ import annotations

from application.core import CamelModel
from application.dtos import Letterhead


class TenantSettingsData(CamelModel):
    timezone: str
    # What a printed document puts at the top of the page (FR-8.1). A logo
    # is not here: it needs a file store, and no document is blocked on it.
    business_name: str | None = None
    address: str | None = None

    @classmethod
    def from_entity(cls, timezone: str, letterhead: Letterhead) -> TenantSettingsData:
        return cls(
            timezone=timezone,
            business_name=letterhead.business_name,
            address=letterhead.address,
        )
