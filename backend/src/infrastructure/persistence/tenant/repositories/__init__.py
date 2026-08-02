"""TenantDB repositories — row ↔ entity mapping stays inside (PRD §7.3).

No query here filters by tenant: the session these are bound to *is* the
tenant, so there is no filter to forget.
"""

from .base import (
    TenantCrudRepository,
    TenantJoinedRepository,
    TenantLedgerRepository,
    TenantRowRepository,
)
from .customer import SqlCustomerRepository
from .device_unit import SqlDeviceUnitRepository
from .device_unit_price_change import SqlDeviceUnitPriceChangeRepository
from .employee import SqlEmployeeRepository
from .financial_transaction import SqlFinancialTransactionRepository
from .location import SqlLocationRepository
from .product import SqlProductRepository
from .product_price_change import SqlProductPriceChangeRepository
from .settings import SETTINGS_ROW_ID, SqlTenantSettingsRepository
from .stock_level import SqlStockLevelRepository
from .stock_movement import SqlStockMovementRepository
from .supplier import SqlSupplierRepository

__all__ = [
    "SETTINGS_ROW_ID",
    "SqlCustomerRepository",
    "SqlDeviceUnitPriceChangeRepository",
    "SqlDeviceUnitRepository",
    "SqlEmployeeRepository",
    "SqlFinancialTransactionRepository",
    "SqlLocationRepository",
    "SqlProductPriceChangeRepository",
    "SqlProductRepository",
    "SqlStockLevelRepository",
    "SqlStockMovementRepository",
    "SqlSupplierRepository",
    "SqlTenantSettingsRepository",
    "TenantCrudRepository",
    "TenantJoinedRepository",
    "TenantLedgerRepository",
    "TenantRowRepository",
]
