"""MasterDB providers: one engine for the app, one session per request."""

from collections.abc import AsyncIterable

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from infrastructure.config import Settings
from infrastructure.types import MasterEngine, MasterSession


class MasterDbProvider(Provider):
    @provide(scope=Scope.APP)
    async def engine(self, settings: Settings) -> AsyncIterable[MasterEngine]:
        engine = create_async_engine(settings.master_db_url)
        yield MasterEngine(engine)
        await engine.dispose()

    @provide(scope=Scope.REQUEST)
    async def session(
        self, engine: MasterEngine
    ) -> AsyncIterable[MasterSession]:
        factory =  async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            yield MasterSession(session)
