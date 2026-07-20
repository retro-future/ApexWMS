"""SQLAlchemy unit of work over one session.

The master/tenant subclasses (``master/uow.py``, ``tenant/uow.py``)
demand the matching session NewType — wiring a UoW to the wrong database
fails where the provider is written, not in production.
"""

from sqlalchemy.ext.asyncio import AsyncSession


class SqlUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
