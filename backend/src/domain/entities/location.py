"""A store, a stockroom, a warehouse (PRD §4.2).

Present from day one even though inter-location transfers are v2: every
stock movement records where it happened, and retrofitting a location
column onto a populated movements table is a migration nobody wants.

Provisioning seeds one ("Main Store", §3.4) so a new tenant can receive
goods before anyone opens the settings screen.
"""

from dataclasses import dataclass
from datetime import datetime

from domain.core import TenantEntity, UuidEntity


@dataclass(eq=False, kw_only=True)
class Location(UuidEntity, TenantEntity):
    name: str
    is_active: bool
    created_at: datetime
