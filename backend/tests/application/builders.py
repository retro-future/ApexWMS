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

from application.use_cases import (
    AcceptInvite,
    ChangePassword,
    ChangeUserRole,
    ClaimsFactory,
    CreateSuperAdmin,
    CreateTenant,
    GetMe,
    GetTenantSettings,
    InviteUser,
    ListUsers,
    Login,
    RefreshTokens,
    TokenIssuer,
    UpdateTenantSettings,
)
from domain.entities import Employee, Tenant, User, UserTenantAccess
from domain.roles import TenantRole
from domain.tenancy import TenantStatus
from tests.application.fakes import (
    FakeClock,
    FakeEmployeeRepository,
    FakeHasher,
    FakeInvitationRepository,
    FakeProvisioner,
    FakeRefreshTokenRepository,
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

    def create_tenant(self) -> CreateTenant:
        return CreateTenant(
            self.tenants,
            self.users,
            self.hasher,
            self.tokens,
            self.provisioner,
            self.clock,
            self.uow,
        )

    def create_superadmin(self) -> CreateSuperAdmin:
        return CreateSuperAdmin(
            self.users, self.app_roles, self.hasher, self.tokens, self.clock, self.uow
        )

    def login(self) -> Login:
        return Login(self.users, self.hasher, self.claims, self.issuer, self.uow)

    def refresh(self) -> RefreshTokens:
        return RefreshTokens(
            self.users,
            self.refresh_tokens,
            self.tokens,
            self.claims,
            self.issuer,
            self.clock,
            self.uow,
        )

    def change_password(self) -> ChangePassword:
        return ChangePassword(
            self.users, self.refresh_tokens, self.hasher, self.clock, self.uow
        )

    def invite_user(self, tenant: Tenant | None = None) -> InviteUser:
        """Bound to one store, as the DI container binds it to the resolved one."""
        store = tenant or self.tenant
        return InviteUser(
            self.scope.employees_at(store.id),
            self.invitations,
            self.tokens,
            self.clock,
            self.uow,
            INVITE_TTL,
            store.id,
        )

    def accept_invite(self) -> AcceptInvite:
        return AcceptInvite(
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

    def get_me(self) -> GetMe:
        return GetMe(self.users)

    def list_users(self) -> ListUsers:
        return ListUsers(self.employees)

    def change_user_role(self) -> ChangeUserRole:
        return ChangeUserRole(self.employees, self.uow)

    def get_tenant_settings(self) -> GetTenantSettings:
        return GetTenantSettings(self.tenant_settings)

    def update_tenant_settings(self) -> UpdateTenantSettings:
        return UpdateTenantSettings(self.tenant_settings, self.uow)

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
        scope=scope,
        uow=FakeUnitOfWork(),
        provisioner=FakeProvisioner(tenants, scope, clock, fail=provisioner_fails),
        tenant=tenant,
    )
