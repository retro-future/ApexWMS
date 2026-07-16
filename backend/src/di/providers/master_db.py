"""MasterDB providers: one engine for the app, one session per request."""

from collections.abc import AsyncIterable

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.config import Settings
from infrastructure.types import MasterEngine, MasterSession


class MasterDbProvider(Provider):
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
