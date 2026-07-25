"""Opening a tenant's database outside a tenant-scoped request (PRD §3.3).

Implements the ``TenantScope`` port — the analogue of the C# reference's
``tenantUow.SetCurrentTenantByIdAsync``. Login needs it because the tenant
is only known once the master ``User`` row has been read, by which point
the request-scoped session has long since had to be built.

Reuses the existing ``TenantEngineRegistry``, so a database opened this way
shares the same bounded pool as one opened at the edge — this is not a
second connection path, just a second way to name the tenant.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.errors import TenantNotActiveError
from application.ports import EmployeeRepository, UnitOfWork
from domain.tenancy import TenantStatus
from infrastructure.config import Settings
from infrastructure.persistence.master.models import TenantDatabaseModel, TenantModel
from infrastructure.persistence.tenant.repositories import SqlEmployeeRepository
from infrastructure.persistence.tenant.uow import SqlTenantUnitOfWork
from infrastructure.tenancy import TenantContext, TenantEngineRegistry, tenant_db_url
from infrastructure.types import MasterSession, TenantSession


@dataclass(frozen=True, slots=True)
class SqlTenantWorkspace:
    """A live session on one tenant's database."""

    employees: EmployeeRepository
    uow: UnitOfWork


class SqlTenantScope:
    """Implements the application ``TenantScope`` port."""

    def __init__(
        self,
        master: MasterSession,
        registry: TenantEngineRegistry,
        settings: Settings,
    ) -> None:
        self._master = master
        self._registry = registry
        self._settings = settings

    @asynccontextmanager
    async def for_tenant(self, tenant_id: UUID) -> AsyncIterator[SqlTenantWorkspace]:
        context = await self._resolve(tenant_id)
        engine = await self._registry.get(context)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            tenant_session = TenantSession(session)
            yield SqlTenantWorkspace(
                employees=SqlEmployeeRepository(tenant_session),
                uow=SqlTenantUnitOfWork(tenant_session),
            )

    async def _resolve(self, tenant_id: UUID) -> TenantContext:
        tenant = await self._master.get(TenantModel, tenant_id)
        database = await self._master.get(TenantDatabaseModel, tenant_id)
        if tenant is None or database is None or tenant.status != TenantStatus.ACTIVE.value:
            # A suspended store is unreachable by this path too, not just at
            # the request edge.
            raise TenantNotActiveError()
        return TenantContext(
            tenant_id=str(tenant_id),
            db_url=tenant_db_url(self._settings.master_db_url, database.db_name),
        )
