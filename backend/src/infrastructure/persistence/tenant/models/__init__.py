"""Per-tenant schema.

Who works at this store (``employees``), what provisioning seeds
(PRD §3.4: the default location and the tenant's settings), the M2
catalog, and M3's two append-only ledgers with the projections they feed.

No table here carries a ``tenant_id``: isolation is physical (PRD §3.1).
"""

from .base import TenantBase
from .customer import CustomerModel
from .device_unit import DeviceUnitModel
from .device_unit_price_change import DeviceUnitPriceChangeModel
from .employee import EmployeeModel
from .financial_transaction import FinancialTransactionModel
from .location import LocationModel
from .product import ProductModel
from .product_price_change import ProductPriceChangeModel
from .settings import TenantSettingsModel
from .stock_level import StockLevelModel
from .stock_movement import StockMovementModel
from .supplier import SupplierModel

__all__ = [
    "CustomerModel",
    "DeviceUnitModel",
    "DeviceUnitPriceChangeModel",
    "EmployeeModel",
    "FinancialTransactionModel",
    "LocationModel",
    "ProductModel",
    "ProductPriceChangeModel",
    "StockLevelModel",
    "StockMovementModel",
    "SupplierModel",
    "TenantBase",
    "TenantSettingsModel",
]
