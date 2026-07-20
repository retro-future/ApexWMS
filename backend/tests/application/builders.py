"""Wires the fakes into ready-to-use use cases.

One place that knows each use case's constructor, so a signature change
touches one file instead of every test.
"""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from application.use_cases import (
    AcceptInvite,
    ChangeUserRole,
    GetMe,
    GetTenantSettings,
    InviteUser,
    ListUsers,
    Login,
    RefreshTokens,
    SignUp,
    TokenIssuer,
    UpdateTenantSettings,
)
from domain.entities import Membership, Tenant, User
from domain.roles import Role
from domain.tenancy import TenantStatus
from tests.application.fakes import (
    FakeClock,
    FakeHasher,
    FakeInvitationRepository,
    FakeMembershipRepository,
    FakeProvisioner,
    FakeRefreshTokenRepository,
    FakeTenantRepository,
    FakeTenantSettingsRepository,
    FakeTokenService,
    FakeUnitOfWork,
    FakeUserRepository,
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
    tenants: FakeTenantRepository
    memberships: FakeMembershipRepository
    refresh_tokens: FakeRefreshTokenRepository
    invitations: FakeInvitationRepository
    tenant_settings: FakeTenantSettingsRepository
    uow: FakeUnitOfWork
    provisioner: FakeProvisioner

    @property
    def issuer(self) -> TokenIssuer:
        return TokenIssuer(self.tokens, self.refresh_tokens, self.clock, REFRESH_TTL)

    def sign_up(self) -> SignUp:
        return SignUp(
            self.users,
            self.tenants,
            self.memberships,
            self.hasher,
            self.provisioner,
            self.issuer,
            self.clock,
            self.uow,
        )

    def login(self) -> Login:
        return Login(
            self.users, self.tenants, self.memberships, self.hasher, self.issuer, self.uow
        )

    def refresh(self) -> RefreshTokens:
        return RefreshTokens(
            self.users,
            self.tenants,
            self.memberships,
            self.refresh_tokens,
            self.tokens,
            self.issuer,
            self.clock,
            self.uow,
        )

    def invite_user(self) -> InviteUser:
        return InviteUser(
            self.users,
            self.memberships,
            self.invitations,
            self.tokens,
            self.clock,
            self.uow,
            INVITE_TTL,
        )

    def accept_invite(self) -> AcceptInvite:
        return AcceptInvite(
            self.users,
            self.memberships,
            self.invitations,
            self.tokens,
            self.hasher,
            self.clock,
            self.uow,
        )

    def get_me(self) -> GetMe:
        return GetMe(self.users)

    def list_users(self) -> ListUsers:
        return ListUsers(self.memberships)

    def change_user_role(self) -> ChangeUserRole:
        return ChangeUserRole(self.memberships, self.uow)

    def get_tenant_settings(self) -> GetTenantSettings:
        return GetTenantSettings(self.tenant_settings)

    def update_tenant_settings(self) -> UpdateTenantSettings:
        return UpdateTenantSettings(self.tenant_settings, self.uow)

    # --- fixture helpers -------------------------------------------------

    def add_tenant(
        self, name: str = "Acme Phones", status: TenantStatus = TenantStatus.ACTIVE
    ) -> Tenant:
        tenant = Tenant(id=uuid4(), name=name, status=status, created_at=self.clock.now())
        self.tenants.by_id[tenant.id] = tenant
        return tenant

    def add_user(
        self, email: str = "owner@example.com", password: str = "hunter2000", **kwargs
    ) -> User:
        user = User(
            id=uuid4(),
            email=email,
            full_name=kwargs.get("full_name", "Test User"),
            password_hash=self.hasher.hash(password) if password else None,
            is_active=kwargs.get("is_active", True),
            created_at=self.clock.now(),
        )
        self.users.by_id[user.id] = user
        return user

    def add_member(self, user: User, tenant: Tenant, role: Role = Role.OWNER) -> Membership:
        membership = Membership(user_id=user.id, tenant_id=tenant.id, role=role)
        self.memberships.items[(user.id, tenant.id)] = membership
        return membership

    async def issue_refresh_for(self, user_id: UUID, tenant_id: UUID, role: Role) -> str:
        """A live refresh token, as if the user had just logged in."""
        pair, _ = await self.issuer.issue(user_id, tenant_id, role)
        return pair.refresh_token


def make_world(provisioner_fails: bool = False) -> World:
    clock = FakeClock()
    users = FakeUserRepository()
    tenants = FakeTenantRepository()
    return World(
        clock=clock,
        hasher=FakeHasher(),
        tokens=FakeTokenService(),
        users=users,
        tenants=tenants,
        memberships=FakeMembershipRepository(users),
        refresh_tokens=FakeRefreshTokenRepository(),
        invitations=FakeInvitationRepository(),
        tenant_settings=FakeTenantSettingsRepository(),
        uow=FakeUnitOfWork(),
        provisioner=FakeProvisioner(tenants, fail=provisioner_fails),
    )
