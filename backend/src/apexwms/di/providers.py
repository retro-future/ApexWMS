"""Dishka providers (PRD §7.5).

Scopes:
    APP     — settings, MasterDB engine, tenant engine registry; later the
              JWT service and PDF renderer.
    REQUEST — MasterDB/TenantDB sessions; later the authenticated user,
              UoW, repositories, and use cases.
"""

from collections.abc import AsyncIterable

from dishka import Provider, Scope, from_context, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apexwms.infrastructure.config import Settings
from apexwms.infrastructure.database import (
    MasterEngine,
    MasterSession,
    TenantEngine,
    TenantSession,
)
from apexwms.infrastructure.tenancy import TenantContext, TenantEngineRegistry


class ConfigProvider(Provider):
    settings = from_context(provides=Settings, scope=Scope.APP)


class MasterDbProvider(Provider):
    """MasterDB: one engine for the app, one session per request."""

    @provide(scope=Scope.APP)
    async def engine(self, settings: Settings) -> AsyncIterable[MasterEngine]:
        engine = create_async_engine(settings.master_db_url)
        yield MasterEngine(engine)
        await engine.dispose()

    @provide(scope=Scope.APP)
    def session_factory(self, engine: MasterEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def session(
        self, factory: async_sessionmaker[AsyncSession]
    ) -> AsyncIterable[MasterSession]:
        async with factory() as session:
            yield MasterSession(session)


class TenantDbProvider(Provider):
    """TenantDB: engines cached in the bounded registry, sessions per request.

    ``TenantContext`` is container context for now; M1 replaces it with a
    provider that derives it from the validated JWT and MasterDB.
    """

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
