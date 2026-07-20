"""Per-tenant schema — the M1 minimum.

Only what provisioning seeds (PRD §3.4): the default location and the
tenant's settings. The catalog and ledgers land in M2/M3.
"""

from .base import TenantBase
from .location import LocationModel
from .settings import TenantSettingsModel

__all__ = [
    "LocationModel",
    "TenantBase",
    "TenantSettingsModel",
]
