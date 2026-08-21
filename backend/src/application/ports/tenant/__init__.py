"""Ports over a tenant's own database: employees, settings, the M2 catalog,
M3's ledgers and their projections, M4's documents, and the unit of work."""

from application.ports.tenant.repositories import (
    CustomerRepository,
    DeviceUnitPriceChangeRepository,
    DeviceUnitRepository,
    DocumentNumberRepository,
    EmployeeRepository,
    FinancialTransactionRepository,
    GoodsReceiptRepository,
    LocationRepository,
    ProductPriceChangeRepository,
    ProductRepository,
    PurchaseOrderRepository,
    SalesInvoiceRepository,
    StockLevelRepository,
    StockMovementRepository,
    SupplierRepository,
    TenantSettingsRepository,
)
from application.ports.tenant.uow import TenantUnitOfWork

__all__ = [
    "CustomerRepository",
    "DeviceUnitPriceChangeRepository",
    "DeviceUnitRepository",
    "DocumentNumberRepository",
    "EmployeeRepository",
    "FinancialTransactionRepository",
    "GoodsReceiptRepository",
    "LocationRepository",
    "ProductPriceChangeRepository",
    "ProductRepository",
    "SalesInvoiceRepository",
    "PurchaseOrderRepository",
    "StockLevelRepository",
    "StockMovementRepository",
    "SupplierRepository",
    "TenantSettingsRepository",
    "TenantUnitOfWork",
]
