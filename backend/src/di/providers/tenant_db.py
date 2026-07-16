"""TenantDB providers: engines cached in the bounded registry, sessions per request.

``TenantContext`` is container context for now; M1 replaces it with a
provider that derives it from the validated JWT and MasterDB.
"""

from collections.abc import AsyncIterable

from dishka import Provider, Scope, from_context, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.config import Settings
from infrastructure.tenancy import TenantContext, TenantEngineRegistry
from infrastructure.types import TenantEngine, TenantSession


class TenantDbProvider(Provider):
    tenant = from_context(provides=TenantContext, scope=Scope.REQUEST)

    @provide(scope=Scope.APP)
    async def registry(self, settings: Settings) -> AsyncIterable[TenantEngineRegistry]:
        registry = TenantEngineRegistry(
            max_engines=settings.max_live_tenant_engines,
            pool_size=settings.tenant_pool_size,
        )
        yield registry
        await registry.dispose_all()

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
