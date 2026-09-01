"""Ports over a tenant's own database: employees, settings, the M2 catalog,
M3's ledgers and their projections, M4's documents, M5b's credit companies
and payments, M6's returns, counts and write-offs, and the unit of work."""

from application.ports.tenant.queries import (
    BelowCostQueries,
    DeviceUnitQueries,
    FinancialTransactionQueries,
    GoodsReceiptQueries,
    MonthEndQueries,
    SalesInvoiceQueries,
    StockMovementQueries,
    StockOnHandQueries,
)
from application.ports.tenant.repositories import (
    CatalogCodeAllocator,
    DocumentNumberAllocator,
    TenantSettingsRepository,
)
from application.ports.tenant.uow import TenantUnitOfWork

__all__ = [
    "BelowCostQueries",
    "CatalogCodeAllocator",
    "DeviceUnitQueries",
    "DocumentNumberAllocator",
    "FinancialTransactionQueries",
    "GoodsReceiptQueries",
    "MonthEndQueries",
    "SalesInvoiceQueries",
    "StockMovementQueries",
    "StockOnHandQueries",
    "TenantSettingsRepository",
    "TenantUnitOfWork",
]
