"""Response payload for tenant settings — the timezone and the letterhead."""

from __future__ import annotations

from application.core import CamelModel
from application.dtos import Letterhead


class TenantSettingsData(CamelModel):
    timezone: str
    # What a printed document puts at the top of the page (FR-8.1). The
    # image itself is not here — it is served as bytes from its own route,
    # so a settings read stays a small JSON body.
    business_name: str | None = None
    address: str | None = None
    has_logo: bool = False
    # Whether the store records the money that physically changed hands
    # (§4.5b). Off, nothing about a sale or a receipt changes.
    runs_till: bool = False

    @classmethod
    def from_entity(
        cls, timezone: str, letterhead: Letterhead, runs_till: bool
    ) -> TenantSettingsData:
        return cls(
            timezone=timezone,
            business_name=letterhead.business_name,
            address=letterhead.address,
            has_logo=letterhead.logo is not None,
            runs_till=runs_till,
        )
