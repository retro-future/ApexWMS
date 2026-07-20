"""Use-case factories (REQUEST scope). Explicit constructors keep the
wiring readable and let settings-derived values (TTLs) be passed as
plain arguments rather than dragging Settings into application code."""

from datetime import timedelta

from dishka import Provider, Scope, provide

from application.ports import (
    Clock,
    InvitationRepository,
    MasterUnitOfWork,
    MembershipRepository,
    PasswordHasher,
    RefreshTokenRepository,
    TenantProvisioner,
    TenantRepository,
    TenantSettingsRepository,
    TenantUnitOfWork,
    TokenService,
    UserRepository,
)
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
from infrastructure.config import Settings


class UseCasesProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def token_issuer(
        self,
        tokens: TokenService,
        refresh_tokens: RefreshTokenRepository,
        clock: Clock,
        settings: Settings,
    ) -> TokenIssuer:
        return TokenIssuer(
            tokens, refresh_tokens, clock, timedelta(days=settings.refresh_token_ttl_days)
        )

    @provide
    def sign_up(
        self,
        users: UserRepository,
        tenants: TenantRepository,
        memberships: MembershipRepository,
        hasher: PasswordHasher,
        provisioner: TenantProvisioner,
        issuer: TokenIssuer,
        clock: Clock,
        uow: MasterUnitOfWork,
    ) -> SignUp:
        return SignUp(users, tenants, memberships, hasher, provisioner, issuer, clock, uow)

    @provide
    def login(
        self,
        users: UserRepository,
        tenants: TenantRepository,
        memberships: MembershipRepository,
        hasher: PasswordHasher,
        issuer: TokenIssuer,
        uow: MasterUnitOfWork,
    ) -> Login:
        return Login(users, tenants, memberships, hasher, issuer, uow)

    @provide
    def refresh_tokens(
        self,
        users: UserRepository,
        tenants: TenantRepository,
        memberships: MembershipRepository,
        refresh_tokens: RefreshTokenRepository,
        tokens: TokenService,
        issuer: TokenIssuer,
        clock: Clock,
        uow: MasterUnitOfWork,
    ) -> RefreshTokens:
        return RefreshTokens(
            users, tenants, memberships, refresh_tokens, tokens, issuer, clock, uow
        )

    @provide
    def invite_user(
        self,
        users: UserRepository,
        memberships: MembershipRepository,
        invitations: InvitationRepository,
        tokens: TokenService,
        clock: Clock,
        uow: MasterUnitOfWork,
        settings: Settings,
    ) -> InviteUser:
        return InviteUser(
            users,
            memberships,
            invitations,
            tokens,
            clock,
            uow,
            timedelta(hours=settings.invite_ttl_hours),
        )

    @provide
    def accept_invite(
        self,
        users: UserRepository,
        memberships: MembershipRepository,
        invitations: InvitationRepository,
        tokens: TokenService,
        hasher: PasswordHasher,
        clock: Clock,
        uow: MasterUnitOfWork,
    ) -> AcceptInvite:
        return AcceptInvite(users, memberships, invitations, tokens, hasher, clock, uow)

    @provide
    def get_me(self, users: UserRepository) -> GetMe:
        return GetMe(users)

    @provide
    def list_users(self, memberships: MembershipRepository) -> ListUsers:
        return ListUsers(memberships)

    @provide
    def change_user_role(
        self, memberships: MembershipRepository, uow: MasterUnitOfWork
    ) -> ChangeUserRole:
        return ChangeUserRole(memberships, uow)

    @provide
    def get_tenant_settings(self, settings: TenantSettingsRepository) -> GetTenantSettings:
        return GetTenantSettings(settings)

    @provide
    def update_tenant_settings(
        self, settings: TenantSettingsRepository, uow: TenantUnitOfWork
    ) -> UpdateTenantSettings:
        return UpdateTenantSettings(settings, uow)
