"""Tenant resolution and the bounded engine registry (PRD §3.2).

Each tenant owns a physical database, so each active tenant needs its own
``AsyncEngine``. The registry keeps at most ``max_engines`` of them alive
(LRU); an evicted engine is disposed, closing its pool. Beyond that ceiling
the answer is PgBouncer, not a bigger cache.
"""

import asyncio
from collections import OrderedDict
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


@dataclass(frozen=True, slots=True)
class TenantContext:
    """The tenant a request is acting on: identity plus where its data lives.

    From M1 on this is derived from the validated JWT plus the
    ``tenant_databases`` row in MasterDB.
    """

    tenant_id: str
    db_url: str


class TenantEngineRegistry:
    """LRU cache of per-tenant engines, bounded to ``max_engines``."""

    def __init__(self, max_engines: int, pool_size: int) -> None:
        self._max_engines = max_engines
        self._pool_size = pool_size
        self._engines: OrderedDict[str, AsyncEngine] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, tenant: TenantContext) -> AsyncEngine:
        async with self._lock:
            engine = self._engines.get(tenant.tenant_id)
            if engine is not None:
                self._engines.move_to_end(tenant.tenant_id)
                return engine

            engine = create_async_engine(tenant.db_url, pool_size=self._pool_size)
            self._engines[tenant.tenant_id] = engine
            evicted = None
            if len(self._engines) > self._max_engines:
                _, evicted = self._engines.popitem(last=False)
        if evicted is not None:
            await evicted.dispose()
        return engine

    async def dispose_all(self) -> None:
        async with self._lock:
            engines = list(self._engines.values())
            self._engines.clear()
        for engine in engines:
            await engine.dispose()
