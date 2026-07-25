"""MasterDB repositories and units of work (REQUEST scope), keyed by their
ports.

Identity is master-side: who a person is, which platform roles they hold,
which stores they may act in, and the tenant registry itself (PRD §3.1).
See ``tenant_repositories.py`` for what a store owns.
"""

from dishka import Provider, Scope, provide

from application.ports import (
    InvitationRepository,
    MasterUnitOfWork,
    RefreshTokenRepository,
    TenantProvisioner,
    TenantRepository,
    UserAppRoleRepository,
    UserRepository,
    UserTenantAccessRepository,
)
from infrastructure.config import Settings
from infrastructure.persistence.master.repositories import (
    SqlInvitationRepository,
    SqlRefreshTokenRepository,
    SqlTenantRepository,
    SqlUserAppRoleRepository,
    SqlUserRepository,
    SqlUserTenantAccessRepository,
)
from infrastructure.persistence.master.uow import SqlMasterUnitOfWork
from infrastructure.provisioning import DefaultTenantProvisioner
from infrastructure.types import MasterEngine, MasterSession


class MasterRepositoriesProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def tenants(self, session: MasterSession) -> TenantRepository:
        return SqlTenantRepository(session)

    @provide
    def users(self, session: MasterSession) -> UserRepository:
        return SqlUserRepository(session)

    @provide
    def app_roles(self, session: MasterSession) -> UserAppRoleRepository:
        return SqlUserAppRoleRepository(session)

    @provide
    def tenant_access(self, session: MasterSession) -> UserTenantAccessRepository:
        return SqlUserTenantAccessRepository(session)

    @provide
    def refresh_tokens(self, session: MasterSession) -> RefreshTokenRepository:
        return SqlRefreshTokenRepository(session)

    @provide
    def invitations(self, session: MasterSession) -> InvitationRepository:
        return SqlInvitationRepository(session)

    @provide
    def master_uow(self, session: MasterSession) -> MasterUnitOfWork:
        return SqlMasterUnitOfWork(session)

    @provide(scope=Scope.APP)
    def provisioner(self, engine: MasterEngine, settings: Settings) -> TenantProvisioner:
        return DefaultTenantProvisioner(engine, settings)
