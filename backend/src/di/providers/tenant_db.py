"""TenantDB providers: engines cached in the bounded registry, sessions per
request.

All tenant-resolution logic lives in ``CurrentTenantAccessor``
(infrastructure/current_tenant_accessor.py) — this provider only constructs
collaborators and delegates (.claude/rules/backend/providers.md,
.claude/rules/backend/tenant-resolution.md).
"""

from collections.abc import AsyncIterable
from uuid import UUID

from dishka import Provider, Scope, provide
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.dtos import RequestedTenant
from application.types import ResolvedTenantId
from infrastructure.config import Settings
from infrastructure.current_tenant_accessor import CurrentTenantAccessor
from infrastructure.security.request_claims import RequestBearerClaims
from infrastructure.tenancy import TenantContext, TenantEngineRegistry
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
    def accessor(
        self,
        request: Request,
        session: MasterSession,
        settings: Settings,
        claims: RequestBearerClaims,
    ) -> CurrentTenantAccessor:
        return CurrentTenantAccessor(request, session, settings, claims)

    @provide(scope=Scope.REQUEST)
    async def tenant(self, accessor: CurrentTenantAccessor) -> TenantContext:
        return await accessor.get_current_tenant()

    @provide(scope=Scope.REQUEST)
    async def tenant_id(self, tenant: TenantContext) -> ResolvedTenantId:
        return ResolvedTenantId(UUID(tenant.tenant_id))

    @provide(scope=Scope.REQUEST)
    async def requested(self, accessor: CurrentTenantAccessor) -> RequestedTenant:
        return await accessor.get_requested_tenant()

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
