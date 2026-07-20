"""TenantDB providers: engines cached in the bounded registry, sessions per request.

``TenantContext`` is derived from the validated JWT plus the MasterDB
``tenant_databases`` row (PRD §3.3) — the tenant is resolved once, here,
at the edge; nothing below this file takes a tenant parameter.
"""

from collections.abc import AsyncIterable

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.dtos import CurrentUser
from application.errors import TenantNotActiveError
from domain.tenancy import TenantStatus
from infrastructure.config import Settings
from infrastructure.persistence.master.models import TenantDatabaseModel, TenantModel
from infrastructure.tenancy import TenantContext, TenantEngineRegistry, tenant_db_url
from infrastructure.types import MasterSession, TenantEngine, TenantSession


class TenantDbProvider(Provider):
    @provide(scope=Scope.APP)
    async def registry(self, settings: Settings) -> AsyncIterable[TenantEngineRegistry]:
        registry = TenantEngineRegistry(
            max_engines=settings.max_live_tenant_engines,
            pool_size=settings.tenant_pool_size,
        )
        yield registry
        await registry.dispose_all()

    @provide(scope=Scope.REQUEST)
    async def tenant(
        self, user: CurrentUser, session: MasterSession, settings: Settings
    ) -> TenantContext:
        tenant = await session.get(TenantModel, user.tenant_id)
        database = await session.get(TenantDatabaseModel, user.tenant_id)
        if tenant is None or database is None or tenant.status != TenantStatus.ACTIVE.value:
            raise TenantNotActiveError()
        return TenantContext(
            tenant_id=str(user.tenant_id),
            db_url=tenant_db_url(settings.master_db_url, database.db_name),
        )

    @provide(scope=Scope.REQUEST)
    async def engine(
        self, registry: TenantEngineRegistry, tenant: TenantContext
    ) -> TenantEngine:
        return TenantEngine(await registry.get(tenant))

    @provide(scope=Scope.REQUEST)
    async def session(self, engine: TenantEngine) -> AsyncIterable[TenantSession]:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            yield TenantSession(session)
