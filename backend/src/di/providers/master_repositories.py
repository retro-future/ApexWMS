"""MasterDB unit of work and the tenant provisioner (PRD §3.1).

The identity and tenant-registry aggregates have moved to the generic
``MasterDbRepository`` in ``master_repository.py``; what stays here is the
transaction boundary and the provisioner, neither of which is an aggregate
repository.
"""

from dishka import Provider, Scope, provide

from application.ports import MasterUnitOfWork, TenantProvisioner
from infrastructure.config import Settings
from infrastructure.persistence.master.uow import SqlMasterUnitOfWork
from infrastructure.provisioning import DefaultTenantProvisioner
from infrastructure.types import MasterEngine, MasterSession


class MasterRepositoriesProvider(Provider):
    scope = Scope.REQUEST

    @provide
    def master_uow(self, session: MasterSession) -> MasterUnitOfWork:
        return SqlMasterUnitOfWork(session)

    @provide(scope=Scope.APP)
    def provisioner(self, engine: MasterEngine, settings: Settings) -> TenantProvisioner:
        return DefaultTenantProvisioner(engine, settings)
