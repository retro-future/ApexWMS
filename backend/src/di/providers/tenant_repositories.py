"""TenantDB query services, the settings row, the number counter, the unit
of work and the tenant scope (REQUEST scope), keyed by their ports.

Aggregate repositories are wired generically in ``tenant_repository.py``;
this module holds only what does not fit that one factory.

``tenant_scope`` lives here rather than in the master module because its
*output*
(``TenantScope``) is about reaching a tenant's data, even though its own
inputs (``MasterSession`` + the engine registry) are master-side — it is
how ``ClaimsFactory``/``AcceptInvite`` open a tenant workspace discovered
mid-request rather than resolved at the edge (PRD §3.3).
"""

from dishka import Provider, Scope, provide

from application.ports import (
    BelowCostQueries,
    CatalogCodeAllocator,
    DeviceUnitQueries,
    DocumentNumberAllocator,
    FinancialTransactionQueries,
    GoodsReceiptQueries,
    MonthEndQueries,
    SalesInvoiceQueries,
    StockMovementQueries,
    StockOnHandQueries,
    TenantScope,
    TenantSettingsRepository,
    TenantUnitOfWork,
)
from infrastructure.config import Settings
from infrastructure.persistence.tenant.catalog_code import SqlCatalogCodeAllocator
from infrastructure.persistence.tenant.document_number import SqlDocumentNumberAllocator
from infrastructure.persistence.tenant.queries import (
    SqlBelowCostQueries,
    SqlDeviceUnitQueries,
    SqlFinancialTransactionQueries,
    SqlGoodsReceiptQueries,
    SqlMonthEndQueries,
    SqlSalesInvoiceQueries,
    SqlStockMovementQueries,
    SqlStockOnHandQueries,
)
from infrastructure.persistence.tenant.settings import SqlTenantSettingsRepository
from infrastructure.persistence.tenant.uow import SqlTenantUnitOfWork
from infrastructure.tenancy import TenantEngineRegistry
from infrastructure.tenant_scope import SqlTenantScope
from infrastructure.types import MasterSession, TenantSession


class TenantRepositoriesProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def tenant_settings(self, session: TenantSession) -> TenantSettingsRepository:
        return SqlTenantSettingsRepository(session)

    # --- M3 ledgers and their projections ------------------------------

    @provide
    def device_unit_queries(self, session: TenantSession) -> DeviceUnitQueries:
        return SqlDeviceUnitQueries(session)

    @provide
    def stock_movement_queries(
        self, session: TenantSession
    ) -> StockMovementQueries:
        return SqlStockMovementQueries(session)

    @provide
    def financial_transaction_queries(
        self, session: TenantSession
    ) -> FinancialTransactionQueries:
        return SqlFinancialTransactionQueries(session)

    @provide
    def stock_on_hand_queries(self, session: TenantSession) -> StockOnHandQueries:
        return SqlStockOnHandQueries(session)

    @provide
    def below_cost_queries(self, session: TenantSession) -> BelowCostQueries:
        return SqlBelowCostQueries(session)

    # --- M4 inbound documents (PRD §4.4, §5.3) -------------------------

    @provide
    def document_numbers(self, session: TenantSession) -> DocumentNumberAllocator:
        return SqlDocumentNumberAllocator(session)

    @provide
    def catalog_codes(self, session: TenantSession) -> CatalogCodeAllocator:
        return SqlCatalogCodeAllocator(session)

    @provide
    def goods_receipt_queries(self, session: TenantSession) -> GoodsReceiptQueries:
        return SqlGoodsReceiptQueries(session)

    @provide
    def sales_invoice_queries(self, session: TenantSession) -> SalesInvoiceQueries:
        return SqlSalesInvoiceQueries(session)

    # --- M9 month-end close (PRD §5.10) --------------------------------

    @provide
    def month_end_queries(self, session: TenantSession) -> MonthEndQueries:
        return SqlMonthEndQueries(session)

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
