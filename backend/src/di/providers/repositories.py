"""Repositories and units of work (REQUEST scope), keyed by their ports."""

from dishka import Provider, Scope, provide

from application.ports import (
    InvitationRepository,
    MasterUnitOfWork,
    MembershipRepository,
    RefreshTokenRepository,
    TenantProvisioner,
    TenantRepository,
    TenantSettingsRepository,
    TenantUnitOfWork,
    UserRepository,
)
from infrastructure.config import Settings
from infrastructure.persistence.master.repositories import (
    SqlInvitationRepository,
    SqlMembershipRepository,
    SqlRefreshTokenRepository,
    SqlTenantRepository,
    SqlUserRepository,
)
from infrastructure.persistence.master.uow import SqlMasterUnitOfWork
from infrastructure.persistence.tenant.repositories import SqlTenantSettingsRepository
from infrastructure.persistence.tenant.uow import SqlTenantUnitOfWork
from infrastructure.provisioning import DefaultTenantProvisioner
from infrastructure.types import MasterEngine, MasterSession, TenantSession


class RepositoriesProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def users(self, session: MasterSession) -> UserRepository:
        return SqlUserRepository(session)

    @provide
    def tenants(self, session: MasterSession) -> TenantRepository:
        return SqlTenantRepository(session)

    @provide
    def memberships(self, session: MasterSession) -> MembershipRepository:
        return SqlMembershipRepository(session)

    @provide
    def refresh_tokens(self, session: MasterSession) -> RefreshTokenRepository:
        return SqlRefreshTokenRepository(session)

    @provide
    def invitations(self, session: MasterSession) -> InvitationRepository:
        return SqlInvitationRepository(session)

    @provide
    def tenant_settings(self, session: TenantSession) -> TenantSettingsRepository:
        return SqlTenantSettingsRepository(session)

    @provide
    def master_uow(self, session: MasterSession) -> MasterUnitOfWork:
        return SqlMasterUnitOfWork(session)

    @provide
    def tenant_uow(self, session: TenantSession) -> TenantUnitOfWork:
        return SqlTenantUnitOfWork(session)

    @provide(scope=Scope.APP)
    def provisioner(self, engine: MasterEngine, settings: Settings) -> TenantProvisioner:
        return DefaultTenantProvisioner(engine, settings)
