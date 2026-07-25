"""TenantDB repositories — row ↔ entity mapping stays inside (PRD §7.3).

No query here filters by tenant: the session these are bound to *is* the
tenant, so there is no filter to forget.
"""

from .base import TenantCrudRepository
from .employee import SqlEmployeeRepository
from .settings import SETTINGS_ROW_ID, SqlTenantSettingsRepository

__all__ = [
    "SETTINGS_ROW_ID",
    "SqlEmployeeRepository",
    "SqlTenantSettingsRepository",
    "TenantCrudRepository",
]
