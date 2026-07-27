"""TenantDB repositories — row ↔ entity mapping stays inside (PRD §7.3).

No query here filters by tenant: the session these are bound to *is* the
tenant, so there is no filter to forget.
"""

from .base import TenantCrudRepository
from .customer import SqlCustomerRepository
from .employee import SqlEmployeeRepository
from .location import SqlLocationRepository
from .product import SqlProductRepository
from .settings import SETTINGS_ROW_ID, SqlTenantSettingsRepository
from .supplier import SqlSupplierRepository

__all__ = [
    "SETTINGS_ROW_ID",
    "SqlCustomerRepository",
    "SqlEmployeeRepository",
    "SqlLocationRepository",
    "SqlProductRepository",
    "SqlSupplierRepository",
    "SqlTenantSettingsRepository",
    "TenantCrudRepository",
]
