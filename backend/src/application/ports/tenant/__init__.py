"""Ports over a tenant's own database: employees, settings, the M2 catalog,
M3's ledgers and their projections, M4's documents, M5b's credit companies
and payments, and the unit of work."""

from application.ports.tenant.repositories import (
    CreditCompanyRepository,
    CustomerRepository,
    DeviceUnitPriceChangeRepository,
    DeviceUnitRepository,
    DocumentNumberRepository,
    EmployeeRepository,
    FinancialTransactionRepository,
    GoodsReceiptRepository,
    LocationRepository,
    PaymentRepository,
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
    "CreditCompanyRepository",
    "CustomerRepository",
    "DeviceUnitPriceChangeRepository",
    "DeviceUnitRepository",
    "DocumentNumberRepository",
    "EmployeeRepository",
    "FinancialTransactionRepository",
    "GoodsReceiptRepository",
    "LocationRepository",
    "PaymentRepository",
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
