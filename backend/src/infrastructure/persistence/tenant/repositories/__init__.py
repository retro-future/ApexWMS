"""TenantDB repositories — row ↔ entity mapping stays inside (PRD §7.3).

No query here filters by tenant: the session these are bound to *is* the
tenant, so there is no filter to forget.
"""

from .base import TenantCrudRepository, TenantRepository
from .credit_company import SqlCreditCompanyRepository
from .customer import SqlCustomerRepository
from .device_unit import SqlDeviceUnitRepository
from .device_unit_price_change import SqlDeviceUnitPriceChangeRepository
from .document_number import SqlDocumentNumberRepository
from .employee import SqlEmployeeRepository
from .financial_transaction import SqlFinancialTransactionRepository
from .goods_receipt import SqlGoodsReceiptRepository
from .location import SqlLocationRepository
from .payment import SqlPaymentRepository
from .product import SqlProductRepository
from .product_price_change import SqlProductPriceChangeRepository
from .sales_invoice import SqlSalesInvoiceRepository
from .sales_report import SqlSalesReportRepository
from .settings import SETTINGS_ROW_ID, SqlTenantSettingsRepository
from .stock_count import SqlStockCountRepository
from .stock_level import SqlStockLevelRepository
from .stock_movement import SqlStockMovementRepository
from .stock_on_hand import SqlStockOnHandRepository
from .write_off import SqlWriteOffRepository

__all__ = [
    "SETTINGS_ROW_ID",
    "SqlCreditCompanyRepository",
    "SqlCustomerRepository",
    "SqlDeviceUnitPriceChangeRepository",
    "SqlDeviceUnitRepository",
    "SqlDocumentNumberRepository",
    "SqlEmployeeRepository",
    "SqlFinancialTransactionRepository",
    "SqlGoodsReceiptRepository",
    "SqlLocationRepository",
    "SqlPaymentRepository",
    "SqlProductPriceChangeRepository",
    "SqlProductRepository",
    "SqlSalesInvoiceRepository",
    "SqlSalesReportRepository",
    "SqlStockCountRepository",
    "SqlStockLevelRepository",
    "SqlStockMovementRepository",
    "SqlStockOnHandRepository",
    "SqlTenantSettingsRepository",
    "SqlWriteOffRepository",
    "TenantCrudRepository",
    "TenantRepository",
]
