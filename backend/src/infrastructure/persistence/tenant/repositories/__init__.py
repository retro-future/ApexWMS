"""TenantDB repositories — row ↔ entity mapping stays inside (PRD §7.3).

No query here filters by tenant: the session these are bound to *is* the
tenant, so there is no filter to forget.
"""

from .base import TenantCrudRepository, TenantRepository
from .customer import SqlCustomerRepository
from .device_unit import SqlDeviceUnitRepository
from .device_unit_price_change import SqlDeviceUnitPriceChangeRepository
from .document_number import SqlDocumentNumberRepository
from .employee import SqlEmployeeRepository
from .financial_transaction import SqlFinancialTransactionRepository
from .goods_receipt import SqlGoodsReceiptRepository
from .location import SqlLocationRepository
from .product import SqlProductRepository
from .product_price_change import SqlProductPriceChangeRepository
from .purchase_order import SqlPurchaseOrderRepository
from .sales_invoice import SqlSalesInvoiceRepository
from .settings import SETTINGS_ROW_ID, SqlTenantSettingsRepository
from .stock_level import SqlStockLevelRepository
from .stock_movement import SqlStockMovementRepository
from .supplier import SqlSupplierRepository

__all__ = [
    "SETTINGS_ROW_ID",
    "SqlCustomerRepository",
    "SqlDeviceUnitPriceChangeRepository",
    "SqlDeviceUnitRepository",
    "SqlDocumentNumberRepository",
    "SqlEmployeeRepository",
    "SqlFinancialTransactionRepository",
    "SqlGoodsReceiptRepository",
    "SqlLocationRepository",
    "SqlProductPriceChangeRepository",
    "SqlProductRepository",
    "SqlPurchaseOrderRepository",
    "SqlSalesInvoiceRepository",
    "SqlStockLevelRepository",
    "SqlStockMovementRepository",
    "SqlSupplierRepository",
    "SqlTenantSettingsRepository",
    "TenantCrudRepository",
    "TenantRepository",
]
