"""Per-tenant schema — the M1 minimum.

Who works at this store (``employees``) plus what provisioning seeds
(PRD §3.4): the default location and the tenant's settings. The catalog
and ledgers land in M2/M3.

No table here carries a ``tenant_id``: isolation is physical (PRD §3.1).
"""

from .base import TenantBase
from .employee import EmployeeModel
from .location import LocationModel
from .settings import TenantSettingsModel

__all__ = [
    "EmployeeModel",
    "LocationModel",
    "TenantBase",
    "TenantSettingsModel",
]
