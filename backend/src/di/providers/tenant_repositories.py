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
    EmployeeRepository,
    TenantScope,
    TenantSettingsRepository,
    TenantUnitOfWork,
)
from infrastructure.config import Settings
from infrastructure.persistence.tenant.repositories import (
    SqlEmployeeRepository,
    SqlTenantSettingsRepository,
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
