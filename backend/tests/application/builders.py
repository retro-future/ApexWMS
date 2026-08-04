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
from application.commands.change_device_unit_condition import (
    ChangeDeviceUnitConditionHandler,
)
from application.commands.change_password import ChangePasswordHandler
from application.commands.change_user_role import ChangeUserRoleHandler
from application.commands.create_customer import CreateCustomerHandler
from application.commands.create_location import CreateLocationHandler
from application.commands.create_product import CreateProductHandler
from application.commands.create_superadmin import CreateSuperAdminHandler
from application.commands.create_supplier import CreateSupplierHandler
from application.commands.create_tenant import CreateTenantHandler
from application.commands.invite_user import InviteUserHandler
from application.commands.login import LoginHandler
from application.commands.refresh_tokens import RefreshTokensHandler
from application.commands.reprice_device_unit import RepriceDeviceUnitHandler
from application.commands.reprice_device_units import RepriceDeviceUnitsHandler
from application.commands.update_customer import UpdateCustomerHandler
from application.commands.update_location import UpdateLocationHandler
from application.commands.update_product import UpdateProductHandler
from application.commands.update_supplier import UpdateSupplierHandler
from application.commands.update_tenant_settings import UpdateTenantSettingsHandler
from application.dtos import CurrentUser, RequestedTenant
from application.queries.get_customer import GetCustomerHandler
from application.queries.get_device_unit import GetDeviceUnitHandler
from application.queries.get_device_unit_price_history import (
    GetDeviceUnitPriceHistoryHandler,
)
from application.queries.get_location import GetLocationHandler
from application.queries.get_me import GetMeHandler
from application.queries.get_product import GetProductHandler
from application.queries.get_product_price_history import GetProductPriceHistoryHandler
from application.queries.get_supplier import GetSupplierHandler
from application.queries.get_tenant_settings import GetTenantSettingsHandler
from application.queries.list_customers import ListCustomersHandler
from application.queries.list_locations import ListLocationsHandler
from application.queries.list_products import ListProductsHandler
from application.queries.list_suppliers import ListSuppliersHandler
from application.queries.list_users import ListUsersHandler
from application.services import (
    ClaimsFactory,
    DeviceUnitLoader,
    DeviceUnitRepricer,
    LedgerPoster,
    ProductRepricer,
    SalePriceParser,
    SlugNormalizer,
    TimezoneValidator,
    TokenIssuer,
)
from domain.entities import Employee, Tenant, User, UserTenantAccess
from domain.enums import TenantRole, TenantStatus
from domain.permissions import Permission
from tests.application.fakes import (
    FakeClock,
    FakeCustomerRepository,
    FakeDeviceUnitPriceChangeRepository,
    FakeDeviceUnitRepository,
    FakeEmployeeRepository,
    FakeFinancialTransactionRepository,
    FakeHasher,
    FakeInvitationRepository,
    FakeLocationRepository,
    FakeProductPriceChangeRepository,
    FakeProductRepository,
    FakeProvisioner,
    FakeRefreshTokenRepository,
    FakeStockLevelRepository,
    FakeStockMovementRepository,
    FakeSupplierRepository,
    FakeTenantRepository,
    FakeTenantScope,
    FakeTenantSettingsRepository,
    FakeTokenService,
    FakeUnitOfWork,
    FakeUserAppRoleRepository,
    FakeUserRepository,
    FakeUserTenantAccessRepository,
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
            self.refresh_tokens,
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
        )

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
