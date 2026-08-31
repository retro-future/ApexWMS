"""Ports — the Protocols use cases depend on (PRD §7.3).

Infrastructure implements these; application never imports the
implementations. This is what lets every use case run against
in-memory fakes with no database.

The generic repository port lives in ``application/common/repository.py``;
``uow.py`` holds the unit-of-work interface. ``master/`` and ``tenant/``
hold the ports specific to each database — mostly query services now, plus
the settings row and the document-number counter.
"""

from application.ports.clock import Clock
from application.ports.documents import (
    InvoiceRenderer,
    MonthEndReportRenderer,
    PurchaseOrderRenderer,
    SupplierReturnRenderer,
)
from application.ports.master import (
    MasterUnitOfWork,
)
from application.ports.provisioning import TenantProvisioner
from application.ports.security import PasswordHasher, TokenService
from application.ports.tenancy import TenantScope, TenantWorkspace
from application.ports.tenant import (
    BelowCostQueries,
    DeviceUnitQueries,
    DocumentNumberAllocator,
    FinancialTransactionQueries,
    GoodsReceiptQueries,
    MonthEndQueries,
    SalesInvoiceQueries,
    StockMovementQueries,
    StockOnHandQueries,
    TenantSettingsRepository,
    TenantUnitOfWork,
)
from application.ports.uow import UnitOfWork

__all__ = [
    "BelowCostQueries",
    "Clock",
    "DeviceUnitQueries",
    "DocumentNumberAllocator",
    "FinancialTransactionQueries",
    "GoodsReceiptQueries",
    "MonthEndQueries",
    "MonthEndReportRenderer",
    "StockMovementQueries",
    "InvoiceRenderer",
    "MasterUnitOfWork",
    "PasswordHasher",
    "SalesInvoiceQueries",
    "PurchaseOrderRenderer",
    "StockOnHandQueries",
    "SupplierReturnRenderer",
    "TenantProvisioner",
    "TenantScope",
    "TenantSettingsRepository",
    "TenantUnitOfWork",
    "TenantWorkspace",
    "TokenService",
    "UnitOfWork",
]
