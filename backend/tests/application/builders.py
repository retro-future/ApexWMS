"""Wires the fakes into ready-to-use use cases.

One place that knows each use case's constructor, so a signature change
touches one file instead of every test.

The World models the platform: master-side identity (`users`, `tenants`,
`invitations`, `refresh_tokens`) plus a `scope` holding one employee
repository per store. `tenant` is the World's default store, and
`employees` is shorthand for its staff.
"""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from application.commands.accept_invite import AcceptInviteHandler
from application.commands.cancel_goods_receipt import CancelGoodsReceiptHandler
from application.commands.cancel_purchase_order import CancelPurchaseOrderHandler
from application.commands.cancel_sales_invoice import CancelSalesInvoiceHandler
from application.commands.cancel_stock_count import CancelStockCountHandler
from application.commands.cancel_supplier_return import CancelSupplierReturnHandler
from application.commands.cancel_write_off import CancelWriteOffHandler
from application.commands.change_device_unit_condition import (
    ChangeDeviceUnitConditionHandler,
)
from application.commands.change_password import ChangePasswordHandler
from application.commands.change_user_role import ChangeUserRoleHandler
from application.commands.close_stock_count import CloseStockCountHandler
from application.commands.confirm_goods_receipt import ConfirmGoodsReceiptHandler
from application.commands.confirm_purchase_order import ConfirmPurchaseOrderHandler
from application.commands.confirm_sales_invoice import ConfirmSalesInvoiceHandler
from application.commands.confirm_stock_count import ConfirmStockCountHandler
from application.commands.confirm_supplier_return import ConfirmSupplierReturnHandler
from application.commands.confirm_write_off import ConfirmWriteOffHandler
from application.commands.count_stock_count_line import CountStockCountLineHandler
from application.commands.create_credit_company import CreateCreditCompanyHandler
from application.commands.create_customer import CreateCustomerHandler
from application.commands.create_goods_receipt import CreateGoodsReceiptHandler
from application.commands.create_location import CreateLocationHandler
from application.commands.create_product import CreateProductHandler
from application.commands.create_purchase_order import CreatePurchaseOrderHandler
from application.commands.create_sales_invoice import CreateSalesInvoiceHandler
from application.commands.create_superadmin import CreateSuperAdminHandler
from application.commands.create_supplier import CreateSupplierHandler
from application.commands.create_supplier_return import CreateSupplierReturnHandler
from application.commands.create_tenant import CreateTenantHandler
from application.commands.create_write_off import CreateWriteOffHandler
from application.commands.invite_user import InviteUserHandler
from application.commands.login import LoginHandler
from application.commands.open_stock_count import OpenStockCountHandler
from application.commands.override_invoice_line_price import (
    OverrideInvoiceLinePriceHandler,
)
from application.commands.price_purchase_order_line import (
    PricePurchaseOrderLineHandler,
)
from application.commands.price_receipt_unit import PriceReceiptUnitHandler
from application.commands.record_payment import RecordPaymentHandler
from application.commands.refresh_tokens import RefreshTokensHandler
from application.commands.reprice_device_unit import RepriceDeviceUnitHandler
from application.commands.reprice_device_units import RepriceDeviceUnitsHandler
from application.commands.reverse_payment import ReversePaymentHandler
from application.commands.scan_invoice_line import ScanInvoiceLineHandler
from application.commands.scan_receipt_unit import ScanReceiptUnitHandler
from application.commands.scan_stock_count_unit import ScanStockCountUnitHandler
from application.commands.scan_supplier_return_line import ScanSupplierReturnLineHandler
from application.commands.scan_write_off_line import ScanWriteOffLineHandler
from application.commands.unscan_invoice_line import UnscanInvoiceLineHandler
from application.commands.unscan_receipt_unit import UnscanReceiptUnitHandler
from application.commands.unscan_stock_count_unit import UnscanStockCountUnitHandler
from application.commands.unscan_supplier_return_line import (
    UnscanSupplierReturnLineHandler,
)
from application.commands.unscan_write_off_line import UnscanWriteOffLineHandler
from application.commands.update_credit_company import UpdateCreditCompanyHandler
from application.commands.update_customer import UpdateCustomerHandler
from application.commands.update_location import UpdateLocationHandler
from application.commands.update_product import UpdateProductHandler
from application.commands.update_supplier import UpdateSupplierHandler
from application.commands.update_tenant_settings import UpdateTenantSettingsHandler
from application.dtos import CurrentUser, RequestedTenant
from application.queries.get_customer import GetCustomerHandler
from application.queries.get_customer_account import GetCustomerAccountHandler
from application.queries.get_device_unit import GetDeviceUnitHandler
from application.queries.get_device_unit_price_history import (
    GetDeviceUnitPriceHistoryHandler,
)
from application.queries.get_goods_receipt import GetGoodsReceiptHandler
from application.queries.get_location import GetLocationHandler
from application.queries.get_me import GetMeHandler
from application.queries.get_month_end_report import GetMonthEndReportHandler
from application.queries.get_product import GetProductHandler
from application.queries.get_product_price_history import GetProductPriceHistoryHandler
from application.queries.get_purchase_order import GetPurchaseOrderHandler
from application.queries.get_sales_invoice import GetSalesInvoiceHandler
from application.queries.get_supplier import GetSupplierHandler
from application.queries.get_tenant_settings import GetTenantSettingsHandler
from application.queries.list_credit_companies import ListCreditCompaniesHandler
from application.queries.list_customers import ListCustomersHandler
from application.queries.list_debtors import ListDebtorsHandler
from application.queries.list_goods_receipts import ListGoodsReceiptsHandler
from application.queries.list_locations import ListLocationsHandler
from application.queries.list_products import ListProductsHandler
from application.queries.list_purchase_orders import ListPurchaseOrdersHandler
from application.queries.list_sales_invoices import ListSalesInvoicesHandler
from application.queries.list_stock_counts import ListStockCountsHandler
from application.queries.list_supplier_returns import ListSupplierReturnsHandler
from application.queries.list_suppliers import ListSuppliersHandler
from application.queries.list_users import ListUsersHandler
from application.queries.list_write_offs import ListWriteOffsHandler
from application.services import (
    BalanceVerifier,
    BelowCostChecker,
    ClaimsFactory,
    CostPoolReader,
    CountPoster,
    DeviceUnitLoader,
    DeviceUnitRepricer,
    DocumentLineBuilder,
    DocumentNumberer,
    InventoryValuer,
    InvoicePoster,
    LedgerPoster,
    MonthEndReporter,
    PaymentPoster,
    PeriodResolver,
    ProductRepricer,
    ReceiptPoster,
    RemovalPoster,
    RemovalScanner,
    SalePriceParser,
    SlugNormalizer,
    TimezoneValidator,
    TokenIssuer,
    UnitOriginGuard,
)
from domain.entities import Employee, Tenant, User, UserTenantAccess
from domain.enums import TenantRole, TenantStatus
from domain.permissions import Permission
from domain.services import UnitProjector
from tests.application.fakes import (
    FakeClock,
    FakeCreditCompanyRepository,
    FakeCustomerRepository,
    FakeDeviceUnitPriceChangeRepository,
    FakeDeviceUnitRepository,
    FakeDocumentNumberAllocator,
    FakeEmployeeRepository,
    FakeFinancialTransactionQueries,
    FakeFinancialTransactionRepository,
    FakeGoodsReceiptQueries,
    FakeGoodsReceiptRepository,
    FakeHasher,
    FakeInvitationRepository,
    FakeLocationRepository,
    FakeMonthEndQueries,
    FakePaymentRepository,
    FakeProductPriceChangeRepository,
    FakeProductRepository,
    FakeProvisioner,
    FakePurchaseOrderRepository,
    FakeRefreshTokenRepository,
    FakeSalesInvoiceQueries,
    FakeSalesInvoiceRepository,
    FakeStockCountRepository,
    FakeStockLevelRepository,
    FakeStockMovementQueries,
    FakeStockMovementRepository,
    FakeSupplierRepository,
    FakeSupplierReturnRepository,
    FakeTenantRepository,
    FakeTenantScope,
    FakeTenantSettingsRepository,
    FakeTokenService,
    FakeUnitOfWork,
    FakeUserAppRoleRepository,
    FakeUserRepository,
    FakeUserTenantAccessRepository,
    FakeWriteOffRepository,
)

REFRESH_TTL = timedelta(days=30)
INVITE_TTL = timedelta(hours=72)


@dataclass
class World:
    """Every fake, plus factories for the use cases under test."""

    clock: FakeClock
    hasher: FakeHasher
    tokens: FakeTokenService
    users: FakeUserRepository
    app_roles: FakeUserAppRoleRepository
    access: FakeUserTenantAccessRepository
    tenants: FakeTenantRepository
    refresh_tokens: FakeRefreshTokenRepository
    invitations: FakeInvitationRepository
    tenant_settings: FakeTenantSettingsRepository
    products: FakeProductRepository
    price_changes: FakeProductPriceChangeRepository
    locations: FakeLocationRepository
    suppliers: FakeSupplierRepository
    customers: FakeCustomerRepository
    units: FakeDeviceUnitRepository
    unit_price_changes: FakeDeviceUnitPriceChangeRepository
    movements: FakeStockMovementRepository
    transactions: FakeFinancialTransactionRepository
    levels: FakeStockLevelRepository
    orders: FakePurchaseOrderRepository
    receipts: FakeGoodsReceiptRepository
    invoices: FakeSalesInvoiceRepository
    credit_companies: FakeCreditCompanyRepository
    payments: FakePaymentRepository
    returns: FakeSupplierReturnRepository
    write_offs: FakeWriteOffRepository
    counts: FakeStockCountRepository
    document_numbers: FakeDocumentNumberAllocator
    scope: FakeTenantScope
    uow: FakeUnitOfWork
    provisioner: FakeProvisioner
    # The World's default store, so most tests never mention a tenant id.
    tenant: Tenant

    @property
    def employees(self) -> FakeEmployeeRepository:
        """Staff at the default store."""
        return self.scope.employees_at(self.tenant.id)

    @property
    def receipt_queries(self) -> FakeGoodsReceiptQueries:
        return FakeGoodsReceiptQueries(self.receipts)

    @property
    def movement_queries(self) -> FakeStockMovementQueries:
        return FakeStockMovementQueries(self.movements, self.units)

    @property
    def transaction_queries(self) -> FakeFinancialTransactionQueries:
        return FakeFinancialTransactionQueries(self.transactions)

    @property
    def claims(self) -> ClaimsFactory:
        return ClaimsFactory(self.app_roles, self.access, self.scope)

    @property
    def issuer(self) -> TokenIssuer:
        return TokenIssuer(self.tokens, self.refresh_tokens, self.clock, REFRESH_TTL)

    def create_tenant(self) -> CreateTenantHandler:
        return CreateTenantHandler(
            self.tenants,
            self.users,
            self.hasher,
            self.tokens,
            self.provisioner,
            self.clock,
            self.uow,
            SlugNormalizer(),
            TimezoneValidator(),
        )

    def create_superadmin(self) -> CreateSuperAdminHandler:
        return CreateSuperAdminHandler(
            self.users, self.app_roles, self.hasher, self.tokens, self.clock, self.uow
        )

    def login(self, requested_tenant_id: UUID | None = None) -> LoginHandler:
        return LoginHandler(
            self.users,
            self.hasher,
            self.claims,
            self.issuer,
            self.uow,
            RequestedTenant(tenant_id=requested_tenant_id),
        )

    def refresh(self, requested_tenant_id: UUID | None = None) -> RefreshTokensHandler:
        return RefreshTokensHandler(
            self.users,
            self.refresh_tokens,
            self.tokens,
            self.claims,
            self.issuer,
            self.clock,
            self.uow,
            RequestedTenant(tenant_id=requested_tenant_id),
        )

    def change_password(self, user_id: UUID) -> ChangePasswordHandler:
        return ChangePasswordHandler(
            self.users,
            self.issuer,
            self.hasher,
            self.clock,
            self.uow,
            CurrentUser(user_id=user_id, permissions=frozenset()),
        )

    def invite_user(
        self, tenant: Tenant | None = None, invited_by: UUID | None = None
    ) -> InviteUserHandler:
        """Bound to one store, as the DI container binds it to the resolved one."""
        store = tenant or self.tenant
        return InviteUserHandler(
            self.scope.employees_at(store.id),
            self.invitations,
            self.tokens,
            self.clock,
            self.uow,
            INVITE_TTL,
            store.id,
            CurrentUser(user_id=invited_by or uuid4(), permissions=frozenset()),
        )

    def accept_invite(self) -> AcceptInviteHandler:
        return AcceptInviteHandler(
            self.users,
            self.invitations,
            self.app_roles,
            self.access,
            self.scope,
            self.tokens,
            self.hasher,
            self.clock,
            self.uow,
        )

    def get_me(self, current: CurrentUser) -> GetMeHandler:
        return GetMeHandler(self.users, current)

    def list_users(self) -> ListUsersHandler:
        return ListUsersHandler(self.employees)

    def change_user_role(self) -> ChangeUserRoleHandler:
        return ChangeUserRoleHandler(self.employees, self.uow)

    def get_tenant_settings(self) -> GetTenantSettingsHandler:
        return GetTenantSettingsHandler(self.tenant_settings)

    def update_tenant_settings(self) -> UpdateTenantSettingsHandler:
        return UpdateTenantSettingsHandler(
            self.tenant_settings, self.uow, TimezoneValidator()
        )

    # --- M2 catalog ------------------------------------------------------

    def repricer(self, actor: UUID | None = None) -> ProductRepricer:
        """*actor* is who the price change will name — pass one when the
        test asserts on authorship, omit it when it is beside the point."""
        return ProductRepricer(
            self.price_changes,
            self.clock,
            CurrentUser(user_id=actor or uuid4(), permissions=frozenset()),
        )

    def create_product(self, actor: UUID | None = None) -> CreateProductHandler:
        return CreateProductHandler(
            self.products, self.clock, self.uow, SalePriceParser(), self.repricer(actor)
        )

    def update_product(self, actor: UUID | None = None) -> UpdateProductHandler:
        return UpdateProductHandler(
            self.products, self.uow, SalePriceParser(), self.repricer(actor)
        )

    def get_product(self) -> GetProductHandler:
        return GetProductHandler(self.products)

    def get_product_price_history(self) -> GetProductPriceHistoryHandler:
        return GetProductPriceHistoryHandler(self.products, self.price_changes)

    # --- M3 ledgers ------------------------------------------------------

    def unit_repricer(self, actor: UUID | None = None) -> DeviceUnitRepricer:
        return DeviceUnitRepricer(
            self.unit_price_changes,
            self.clock,
            CurrentUser(user_id=actor or uuid4(), permissions=frozenset()),
        )

    def device_unit_loader(self) -> DeviceUnitLoader:
        return DeviceUnitLoader(self.units, self.products)

    def _as(self, actor: UUID | None, *permissions: Permission) -> CurrentUser:
        """The acting identity a unit handler shapes its response for
        (FR-1.7) — pass ``Permission.COST_VIEW`` to see cost."""
        return CurrentUser(user_id=actor or uuid4(), permissions=frozenset(permissions))

    def get_device_unit(
        self, actor: UUID | None = None, *permissions: Permission
    ) -> GetDeviceUnitHandler:
        return GetDeviceUnitHandler(self.device_unit_loader(), self._as(actor, *permissions))

    def get_device_unit_price_history(self) -> GetDeviceUnitPriceHistoryHandler:
        return GetDeviceUnitPriceHistoryHandler(self.units, self.unit_price_changes)

    def reprice_device_unit(
        self, actor: UUID | None = None, *permissions: Permission
    ) -> RepriceDeviceUnitHandler:
        return RepriceDeviceUnitHandler(
            self.units,
            self.device_unit_loader(),
            self.unit_repricer(actor),
            SalePriceParser(),
            self.uow,
            self._as(actor, *permissions),
        )

    def reprice_device_units(self, actor: UUID | None = None) -> RepriceDeviceUnitsHandler:
        return RepriceDeviceUnitsHandler(
            self.units,
            self.products,
            self.unit_repricer(actor),
            SalePriceParser(),
            self.uow,
        )

    def change_device_unit_condition(
        self, actor: UUID | None = None, *permissions: Permission
    ) -> ChangeDeviceUnitConditionHandler:
        return ChangeDeviceUnitConditionHandler(
            self.units, self.device_unit_loader(), self.uow, self._as(actor, *permissions)
        )

    def poster(self, actor: UUID | None = None) -> LedgerPoster:
        """*actor* is who the ledger rows will name — pass one when the
        test asserts on authorship (§4.3 rule 3), omit it otherwise."""
        return LedgerPoster(
            self.movements,
            self.transactions,
            self.levels,
            self.units,
            self.clock,
            CurrentUser(user_id=actor or uuid4(), permissions=frozenset()),
            UnitProjector(),
        )

    def cost_pools(self) -> CostPoolReader:
        return CostPoolReader(self.products, self.movements, self.transactions)

    @property
    def cost_pool_reader(self) -> CostPoolReader:
        return self.cost_pools()

    # --- M4 purchasing & receiving ---

    def numberer(self) -> DocumentNumberer:
        return DocumentNumberer(self.document_numbers, self.clock)

    def line_builder(self) -> DocumentLineBuilder:
        return DocumentLineBuilder(self.products)

    @property
    def invoice_queries(self) -> FakeSalesInvoiceQueries:
        return FakeSalesInvoiceQueries(self.invoices, self.payments)

    def receipt_poster(self, actor: UUID | None = None) -> ReceiptPoster:
        return ReceiptPoster(
            self.units, self.unit_repricer(actor), self.poster(actor), self.clock
        )

    def create_purchase_order(self, actor: UUID | None = None) -> CreatePurchaseOrderHandler:
        return CreatePurchaseOrderHandler(
            self.orders,
            self.suppliers,
            self.line_builder(),
            self.numberer(),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def price_purchase_order_line(
        self, actor: UUID | None = None
    ) -> PricePurchaseOrderLineHandler:
        return PricePurchaseOrderLineHandler(
            self.orders,
            self.uow,
            self._as(actor),
        )

    def confirm_purchase_order(
        self, actor: UUID | None = None
    ) -> ConfirmPurchaseOrderHandler:
        return ConfirmPurchaseOrderHandler(
            self.orders,
            self.receipt_queries,
            self.clock,
            self.uow,
            self._as(actor),
        )

    def cancel_purchase_order(self, actor: UUID | None = None) -> CancelPurchaseOrderHandler:
        return CancelPurchaseOrderHandler(
            self.orders,
            self.receipt_queries,
            self.clock,
            self.uow,
            self._as(actor),
        )

    def get_purchase_order(self) -> GetPurchaseOrderHandler:
        return GetPurchaseOrderHandler(self.orders, self.receipt_queries)

    def list_purchase_orders(self) -> ListPurchaseOrdersHandler:
        return ListPurchaseOrdersHandler(self.orders, self.receipt_queries)

    def create_goods_receipt(self, actor: UUID | None = None) -> CreateGoodsReceiptHandler:
        return CreateGoodsReceiptHandler(
            self.receipts,
            self.receipt_queries,
            self.orders,
            self.suppliers,
            self.customers,
            self.locations,
            self.line_builder(),
            self.numberer(),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def scan_receipt_unit(
        self, actor: UUID | None = None, *permissions: Permission
    ) -> ScanReceiptUnitHandler:
        return ScanReceiptUnitHandler(
            self.receipts, self.units, self.uow,
            self._as(actor, *permissions),
        )

    def price_receipt_unit(
        self, actor: UUID | None = None, *permissions: Permission
    ) -> PriceReceiptUnitHandler:
        return PriceReceiptUnitHandler(
            self.receipts, self.uow, self._as(actor, *permissions)
        )

    def unscan_receipt_unit(self) -> UnscanReceiptUnitHandler:
        return UnscanReceiptUnitHandler(self.receipts, self.uow)

    def confirm_goods_receipt(
        self, actor: UUID | None = None, *permissions: Permission
    ) -> ConfirmGoodsReceiptHandler:
        return ConfirmGoodsReceiptHandler(
            self.receipts,
            self.receipt_poster(actor),
            BelowCostChecker(self.products, self.cost_pool_reader),
            self.clock,
            self.uow,
            self._as(actor, *permissions),
        )

    def cancel_goods_receipt(
        self, actor: UUID | None = None, *permissions: Permission
    ) -> CancelGoodsReceiptHandler:
        return CancelGoodsReceiptHandler(
            self.receipts,
            self.poster(actor),
            self.clock,
            self.uow,
            self._as(actor, *permissions),
        )

    def get_goods_receipt(
        self, actor: UUID | None = None, *permissions: Permission
    ) -> GetGoodsReceiptHandler:
        return GetGoodsReceiptHandler(self.receipts, self._as(actor, *permissions))

    def list_goods_receipts(
        self, actor: UUID | None = None, *permissions: Permission
    ) -> ListGoodsReceiptsHandler:
        return ListGoodsReceiptsHandler(self.receipts, self._as(actor, *permissions))

    def list_products(self) -> ListProductsHandler:
        return ListProductsHandler(self.products)

    def create_location(self) -> CreateLocationHandler:
        return CreateLocationHandler(self.locations, self.clock, self.uow)

    def update_location(self) -> UpdateLocationHandler:
        return UpdateLocationHandler(self.locations, self.uow)

    def get_location(self) -> GetLocationHandler:
        return GetLocationHandler(self.locations)

    def list_locations(self) -> ListLocationsHandler:
        return ListLocationsHandler(self.locations)

    def create_supplier(self) -> CreateSupplierHandler:
        return CreateSupplierHandler(self.suppliers, self.clock, self.uow)

    def update_supplier(self) -> UpdateSupplierHandler:
        return UpdateSupplierHandler(self.suppliers, self.uow)

    def get_supplier(self) -> GetSupplierHandler:
        return GetSupplierHandler(self.suppliers)

    def list_suppliers(self) -> ListSuppliersHandler:
        return ListSuppliersHandler(self.suppliers)

    def create_customer(self) -> CreateCustomerHandler:
        return CreateCustomerHandler(self.customers, self.clock, self.uow)

    def update_customer(self) -> UpdateCustomerHandler:
        return UpdateCustomerHandler(self.customers, self.uow)

    def get_customer(self) -> GetCustomerHandler:
        return GetCustomerHandler(self.customers)

    def list_customers(self) -> ListCustomersHandler:
        return ListCustomersHandler(self.customers)

    # --- fixture helpers -------------------------------------------------

    def add_tenant(
        self,
        name: str = "Beta Mobile",
        slug: str = "beta",
        status: TenantStatus = TenantStatus.ACTIVE,
    ) -> Tenant:
        tenant = Tenant(
            id=uuid4(), name=name, slug=slug, status=status, created_at=self.clock.now()
        )
        self.tenants.by_id[tenant.id] = tenant
        return tenant

    def add_user(
        self,
        email: str = "owner@example.com",
        password: str = "hunter2000",
        role: TenantRole | None = TenantRole.OWNER,
        tenant: Tenant | None = None,
        **kwargs,
    ) -> User:
        """A master identity plus, unless ``role`` is None, a presence at a store.

        ``role=None`` builds a platform operator: no home store, no employee.
        """
        home = tenant if tenant is not None else (self.tenant if role else None)
        user = User(
            id=uuid4(),
            email=email,
            full_name=kwargs.get("full_name", "Test User"),
            password_hash=self.hasher.hash(password) if password else None,
            tenant_id=home.id if home else None,
            is_active=kwargs.get("is_active", True),
            must_change_password=kwargs.get("must_change_password", False),
            created_at=self.clock.now(),
        )
        self.users.by_id[user.id] = user
        if role is not None and home is not None:
            self.add_employee(user, home, role)
        return user

    def add_employee(
        self, user: User, tenant: Tenant, role: TenantRole = TenantRole.OWNER
    ) -> Employee:
        """A presence at one store, keyed by the master user id."""
        employee = Employee(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=role,
            is_active=True,
            created_at=self.clock.now(),
        )
        self.scope.employees_at(tenant.id).by_id[employee.id] = employee
        return employee

    def grant_access(self, user: User, tenant: Tenant) -> UserTenantAccess:
        grant = UserTenantAccess(id=uuid4(), user_id=user.id, tenant_id=tenant.id)
        self.access.by_id[grant.id] = grant
        return grant

    async def issue_refresh_for(
        self, user: User, requested_tenant_id: UUID | None = None
    ) -> str:
        """A live refresh token, as if the user had just logged in."""
        claims = await self.claims.build(user, requested_tenant_id)
        pair, _ = await self.issuer.issue(user.id, claims)
        return pair.refresh_token

    # --- M5 outbound ---

    def invoice_poster(self, actor: UUID | None = None) -> InvoicePoster:
        return InvoicePoster(
            self.units, self.products, self.levels, self.cost_pools(), self.poster(actor)
        )

    def create_sales_invoice(self, actor: UUID | None = None) -> CreateSalesInvoiceHandler:
        return CreateSalesInvoiceHandler(
            self.invoices,
            self.locations,
            self.customers,
            self.numberer(),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def scan_invoice_line(self) -> ScanInvoiceLineHandler:
        return ScanInvoiceLineHandler(
            self.invoices,
            self.device_unit_loader(),
            self.products,
            self.uow,
        )

    def override_invoice_line_price(
        self, actor: UUID | None = None
    ) -> OverrideInvoiceLinePriceHandler:
        return OverrideInvoiceLinePriceHandler(
            self.invoices, self.uow, self._as(actor)
        )

    def unscan_invoice_line(self) -> UnscanInvoiceLineHandler:
        return UnscanInvoiceLineHandler(self.invoices, self.uow)

    def confirm_sales_invoice(self, actor: UUID | None = None) -> ConfirmSalesInvoiceHandler:
        return ConfirmSalesInvoiceHandler(
            self.invoices,
            self.credit_companies,
            self.payments,
            self.invoice_poster(actor),
            self.payment_poster(actor),
            SalePriceParser(),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def cancel_sales_invoice(self, actor: UUID | None = None) -> CancelSalesInvoiceHandler:
        return CancelSalesInvoiceHandler(
            self.invoices,
            self.payments,
            self.poster(actor),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def get_sales_invoice(self) -> GetSalesInvoiceHandler:
        return GetSalesInvoiceHandler(self.invoices, self.payments)

    def list_sales_invoices(self) -> ListSalesInvoicesHandler:
        return ListSalesInvoicesHandler(self.invoices, self.payments)

    # --- M5b credit sales & customer debt ---

    def payment_poster(self, actor: UUID | None = None) -> PaymentPoster:
        return PaymentPoster(self.payments, self.poster(actor), self.clock, self._as(actor))

    def create_credit_company(self) -> CreateCreditCompanyHandler:
        return CreateCreditCompanyHandler(self.credit_companies, self.clock, self.uow)

    def update_credit_company(self) -> UpdateCreditCompanyHandler:
        return UpdateCreditCompanyHandler(self.credit_companies, self.uow)

    def list_credit_companies(self) -> ListCreditCompaniesHandler:
        return ListCreditCompaniesHandler(self.credit_companies)

    def record_payment(self, actor: UUID | None = None) -> RecordPaymentHandler:
        return RecordPaymentHandler(
            self.invoices,
            self.payment_poster(actor),
            self.payments,
            SalePriceParser(),
            self.uow,
        )

    def reverse_payment(self, actor: UUID | None = None) -> ReversePaymentHandler:
        return ReversePaymentHandler(
            self.payments, self.invoices, self.payment_poster(actor), self.uow
        )

    def get_customer_account(self) -> GetCustomerAccountHandler:
        return GetCustomerAccountHandler(self.customers, self.invoice_queries, self.clock)

    def list_debtors(self) -> ListDebtorsHandler:
        return ListDebtorsHandler(self.invoice_queries, self.clock)

    # --- M6 returns, counts & write-offs ---

    def unit_origin_guard(self) -> UnitOriginGuard:
        return UnitOriginGuard(self.receipt_queries)

    def removal_poster(self, actor: UUID | None = None) -> RemovalPoster:
        return RemovalPoster(
            self.units,
            self.products,
            self.levels,
            self.cost_pools(),
            self.poster(actor),
            self.unit_origin_guard(),
        )

    def removal_scanner(self) -> RemovalScanner:
        return RemovalScanner(
            self.device_unit_loader(), self.products, self.unit_origin_guard()
        )

    def count_poster(self, actor: UUID | None = None) -> CountPoster:
        return CountPoster(
            self.units,
            self.products,
            self.levels,
            self.cost_pools(),
            self.poster(actor),
            self.clock,
        )

    def create_supplier_return(
        self, actor: UUID | None = None
    ) -> CreateSupplierReturnHandler:
        return CreateSupplierReturnHandler(
            self.returns,
            self.suppliers,
            self.locations,
            self.numberer(),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def scan_supplier_return_line(self) -> ScanSupplierReturnLineHandler:
        return ScanSupplierReturnLineHandler(
            self.returns, self.removal_scanner(), self.uow
        )

    def unscan_supplier_return_line(self) -> UnscanSupplierReturnLineHandler:
        return UnscanSupplierReturnLineHandler(
            self.returns, self.units, self.uow
        )

    def confirm_supplier_return(
        self, actor: UUID | None = None
    ) -> ConfirmSupplierReturnHandler:
        return ConfirmSupplierReturnHandler(
            self.returns,
            self.removal_poster(actor),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def cancel_supplier_return(
        self, actor: UUID | None = None
    ) -> CancelSupplierReturnHandler:
        return CancelSupplierReturnHandler(
            self.returns,
            self.poster(actor),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def list_supplier_returns(self) -> ListSupplierReturnsHandler:
        return ListSupplierReturnsHandler(self.returns)

    def create_write_off(self, actor: UUID | None = None) -> CreateWriteOffHandler:
        return CreateWriteOffHandler(
            self.write_offs,
            self.locations,
            self.numberer(),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def scan_write_off_line(self) -> ScanWriteOffLineHandler:
        return ScanWriteOffLineHandler(
            self.write_offs, self.removal_scanner(), self.uow
        )

    def unscan_write_off_line(self) -> UnscanWriteOffLineHandler:
        return UnscanWriteOffLineHandler(self.write_offs, self.units, self.uow)

    def confirm_write_off(self, actor: UUID | None = None) -> ConfirmWriteOffHandler:
        return ConfirmWriteOffHandler(
            self.write_offs,
            self.removal_poster(actor),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def cancel_write_off(self, actor: UUID | None = None) -> CancelWriteOffHandler:
        return CancelWriteOffHandler(
            self.write_offs,
            self.poster(actor),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def list_write_offs(self) -> ListWriteOffsHandler:
        return ListWriteOffsHandler(self.write_offs)

    def open_stock_count(self, actor: UUID | None = None) -> OpenStockCountHandler:
        return OpenStockCountHandler(
            self.counts,
            self.units,
            self.levels,
            self.locations,
            self.numberer(),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def scan_stock_count_unit(
        self, actor: UUID | None = None, *permissions: Permission
    ) -> ScanStockCountUnitHandler:
        return ScanStockCountUnitHandler(
            self.counts,
            self.units,
            self.products,
            self.uow,
            self._as(actor, *permissions),
        )

    def unscan_stock_count_unit(self) -> UnscanStockCountUnitHandler:
        return UnscanStockCountUnitHandler(self.counts, self.uow)

    def count_stock_count_line(
        self, actor: UUID | None = None
    ) -> CountStockCountLineHandler:
        return CountStockCountLineHandler(self.counts, self.uow, self._as(actor))

    def close_stock_count(self, actor: UUID | None = None) -> CloseStockCountHandler:
        return CloseStockCountHandler(
            self.counts, self.clock, self.uow, self._as(actor)
        )

    def confirm_stock_count(self, actor: UUID | None = None) -> ConfirmStockCountHandler:
        return ConfirmStockCountHandler(
            self.counts,
            self.count_poster(actor),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def cancel_stock_count(self, actor: UUID | None = None) -> CancelStockCountHandler:
        return CancelStockCountHandler(
            self.counts,
            self.poster(actor),
            self.clock,
            self.uow,
            self._as(actor),
        )

    def list_stock_counts(
        self, actor: UUID | None = None, *permissions: Permission
    ) -> ListStockCountsHandler:
        return ListStockCountsHandler(self.counts, self._as(actor, *permissions))

    def balance_verifier(self) -> BalanceVerifier:
        return BalanceVerifier(self.invoices, self.payments, self.transaction_queries)

    # --- M9 month-end close ---

    @property
    def month_end_queries(self) -> FakeMonthEndQueries:
        return FakeMonthEndQueries(
            self.invoices, self.payments, self.credit_companies, self.transactions
        )

    def period_resolver(self) -> PeriodResolver:
        return PeriodResolver(self.tenant_settings)

    def inventory_valuer(self) -> InventoryValuer:
        return InventoryValuer(self.movement_queries, self.cost_pools())

    def month_end_reporter(self) -> MonthEndReporter:
        return MonthEndReporter(
            self.period_resolver(),
            self.transaction_queries,
            self.month_end_queries,
            self.inventory_valuer(),
            self.balance_verifier(),
        )

    def month_end_report(self) -> GetMonthEndReportHandler:
        return GetMonthEndReportHandler(self.month_end_reporter())


def make_world(provisioner_fails: bool = False) -> World:
    clock = FakeClock()
    tenants = FakeTenantRepository()
    scope = FakeTenantScope(tenants)
    tenant = Tenant(
        id=uuid4(),
        name="Acme Phones",
        slug="acme",
        status=TenantStatus.ACTIVE,
        created_at=clock.now(),
    )
    tenants.by_id[tenant.id] = tenant
    invoices = FakeSalesInvoiceRepository()
    payments = FakePaymentRepository()
    return World(
        clock=clock,
        hasher=FakeHasher(),
        tokens=FakeTokenService(),
        users=FakeUserRepository(),
        app_roles=FakeUserAppRoleRepository(),
        access=FakeUserTenantAccessRepository(),
        tenants=tenants,
        refresh_tokens=FakeRefreshTokenRepository(),
        invitations=FakeInvitationRepository(),
        tenant_settings=FakeTenantSettingsRepository(),
        products=FakeProductRepository(),
        price_changes=FakeProductPriceChangeRepository(),
        units=FakeDeviceUnitRepository(),
        unit_price_changes=FakeDeviceUnitPriceChangeRepository(),
        orders=FakePurchaseOrderRepository(),
        receipts=FakeGoodsReceiptRepository(),
        invoices=invoices,
        credit_companies=FakeCreditCompanyRepository(),
        payments=payments,
        returns=FakeSupplierReturnRepository(),
        write_offs=FakeWriteOffRepository(),
        counts=FakeStockCountRepository(),
        document_numbers=FakeDocumentNumberAllocator(),
        movements=FakeStockMovementRepository(),
        transactions=FakeFinancialTransactionRepository(),
        levels=FakeStockLevelRepository(),
        locations=FakeLocationRepository(),
        suppliers=FakeSupplierRepository(),
        customers=FakeCustomerRepository(),
        scope=scope,
        uow=FakeUnitOfWork(),
        provisioner=FakeProvisioner(tenants, scope, clock, fail=provisioner_fails),
        tenant=tenant,
    )
