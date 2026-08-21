"""Ports — the Protocols use cases depend on (PRD §7.3).

Infrastructure implements these; application never imports the
implementations. This is what lets every use case run against
in-memory fakes with no database.

Layout mirrors the two databases: ``repository.py``/``uow.py`` hold the
generic interfaces, ``master/`` the tenant registry and identity,
``tenant/`` what a store owns — including who works there.
"""

from application.ports.clock import Clock
from application.ports.documents import InvoiceRenderer
from application.ports.master import (
    InvitationRepository,
    MasterUnitOfWork,
    RefreshTokenRepository,
    TenantRepository,
    UserAppRoleRepository,
    UserRepository,
    UserTenantAccessRepository,
)
from application.ports.provisioning import TenantProvisioner
from application.ports.repository import AppendOnlyRepository, Repository
from application.ports.security import PasswordHasher, TokenService
from application.ports.tenancy import TenantScope, TenantWorkspace
from application.ports.tenant import (
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
    TenantUnitOfWork,
)
from application.ports.uow import UnitOfWork

__all__ = [
    "AppendOnlyRepository",
    "Clock",
    "CustomerRepository",
    "DeviceUnitPriceChangeRepository",
    "DeviceUnitRepository",
    "DocumentNumberRepository",
    "EmployeeRepository",
    "FinancialTransactionRepository",
    "GoodsReceiptRepository",
    "InvitationRepository",
    "InvoiceRenderer",
    "LocationRepository",
    "MasterUnitOfWork",
    "PasswordHasher",
    "ProductPriceChangeRepository",
    "ProductRepository",
    "SalesInvoiceRepository",
    "PurchaseOrderRepository",
    "RefreshTokenRepository",
    "Repository",
    "StockLevelRepository",
    "StockMovementRepository",
    "SupplierRepository",
    "TenantProvisioner",
    "TenantRepository",
    "TenantScope",
    "TenantSettingsRepository",
    "TenantUnitOfWork",
    "TenantWorkspace",
    "TokenService",
    "UnitOfWork",
    "UserAppRoleRepository",
    "UserRepository",
    "UserTenantAccessRepository",
]
