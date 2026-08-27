"""TenantDB repositories and units of work (REQUEST scope), keyed by their
ports.

What a store owns — including who works there (PRD §3.1). See
``master_repositories.py`` for master-side identity and the tenant
registry.

``tenant_scope`` lives here rather than there because its *output*
(``TenantScope``) is about reaching a tenant's data, even though its own
inputs (``MasterSession`` + the engine registry) are master-side — it is
how ``ClaimsFactory``/``AcceptInvite`` open a tenant workspace discovered
mid-request rather than resolved at the edge (PRD §3.3).
"""

from dishka import Provider, Scope, provide

from application.ports import (
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
    SalesReportRepository,
    StockCountRepository,
    StockLevelRepository,
    StockMovementRepository,
    StockOnHandRepository,
    SupplierRepository,
    SupplierReturnRepository,
    TenantScope,
    TenantSettingsRepository,
    TenantUnitOfWork,
    WriteOffRepository,
)
from infrastructure.config import Settings
from infrastructure.persistence.tenant.repositories import (
    SqlCreditCompanyRepository,
    SqlCustomerRepository,
    SqlDeviceUnitPriceChangeRepository,
    SqlDeviceUnitRepository,
    SqlDocumentNumberRepository,
    SqlEmployeeRepository,
    SqlFinancialTransactionRepository,
    SqlGoodsReceiptRepository,
    SqlLocationRepository,
    SqlPaymentRepository,
    SqlProductPriceChangeRepository,
    SqlProductRepository,
    SqlPurchaseOrderRepository,
    SqlSalesInvoiceRepository,
    SqlSalesReportRepository,
    SqlStockCountRepository,
    SqlStockLevelRepository,
    SqlStockMovementRepository,
    SqlStockOnHandRepository,
    SqlSupplierRepository,
    SqlSupplierReturnRepository,
    SqlTenantSettingsRepository,
    SqlWriteOffRepository,
)
from infrastructure.persistence.tenant.uow import SqlTenantUnitOfWork
from infrastructure.tenancy import TenantEngineRegistry
from infrastructure.tenant_scope import SqlTenantScope
from infrastructure.types import MasterSession, TenantSession


class TenantRepositoriesProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def employees(self, session: TenantSession) -> EmployeeRepository:
        return SqlEmployeeRepository(session)

    @provide
    def tenant_settings(self, session: TenantSession) -> TenantSettingsRepository:
        return SqlTenantSettingsRepository(session)

    @provide
    def products(self, session: TenantSession) -> ProductRepository:
        return SqlProductRepository(session)

    @provide
    def product_price_changes(self, session: TenantSession) -> ProductPriceChangeRepository:
        return SqlProductPriceChangeRepository(session)

    @provide
    def locations(self, session: TenantSession) -> LocationRepository:
        return SqlLocationRepository(session)

    @provide
    def suppliers(self, session: TenantSession) -> SupplierRepository:
        return SqlSupplierRepository(session)

    @provide
    def customers(self, session: TenantSession) -> CustomerRepository:
        return SqlCustomerRepository(session)

    @provide
    def credit_companies(self, session: TenantSession) -> CreditCompanyRepository:
        return SqlCreditCompanyRepository(session)

    # --- M3 ledgers and their projections ------------------------------

    @provide
    def device_units(self, session: TenantSession) -> DeviceUnitRepository:
        return SqlDeviceUnitRepository(session)

    @provide
    def device_unit_price_changes(
        self, session: TenantSession
    ) -> DeviceUnitPriceChangeRepository:
        return SqlDeviceUnitPriceChangeRepository(session)

    @provide
    def stock_movements(self, session: TenantSession) -> StockMovementRepository:
        return SqlStockMovementRepository(session)

    @provide
    def financial_transactions(
        self, session: TenantSession
    ) -> FinancialTransactionRepository:
        return SqlFinancialTransactionRepository(session)

    @provide
    def stock_levels(self, session: TenantSession) -> StockLevelRepository:
        return SqlStockLevelRepository(session)

    @provide
    def stock_on_hand(self, session: TenantSession) -> StockOnHandRepository:
        return SqlStockOnHandRepository(session)

    # --- M4 inbound documents (PRD §4.4, §5.3) -------------------------

    @provide
    def document_numbers(self, session: TenantSession) -> DocumentNumberRepository:
        return SqlDocumentNumberRepository(session)

    @provide
    def purchase_orders(self, session: TenantSession) -> PurchaseOrderRepository:
        return SqlPurchaseOrderRepository(session)

    @provide
    def goods_receipts(self, session: TenantSession) -> GoodsReceiptRepository:
        return SqlGoodsReceiptRepository(session)

    @provide
    def sales_invoices(self, session: TenantSession) -> SalesInvoiceRepository:
        return SqlSalesInvoiceRepository(session)

    @provide
    def sales_reports(self, session: TenantSession) -> SalesReportRepository:
        return SqlSalesReportRepository(session)

    # --- M5b credit sales (PRD §4.7) -----------------------------------

    @provide
    def payments(self, session: TenantSession) -> PaymentRepository:
        return SqlPaymentRepository(session)

    # --- M6 returns, counts and write-offs (PRD §5.5, §5.6) -------------

    @provide
    def supplier_returns(self, session: TenantSession) -> SupplierReturnRepository:
        return SqlSupplierReturnRepository(session)

    @provide
    def write_offs(self, session: TenantSession) -> WriteOffRepository:
        return SqlWriteOffRepository(session)

    @provide
    def stock_counts(self, session: TenantSession) -> StockCountRepository:
        return SqlStockCountRepository(session)

    @provide
    def tenant_uow(self, session: TenantSession) -> TenantUnitOfWork:
        return SqlTenantUnitOfWork(session)

    @provide
    def tenant_scope(
        self,
        session: MasterSession,
        registry: TenantEngineRegistry,
        settings: Settings,
    ) -> TenantScope:
        return SqlTenantScope(session, registry, settings)
