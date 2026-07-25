"""The generic CRUD template implementing ``Repository[EntityT, KeyT]``.

Concrete repositories supply the row ↔ entity mapping through the hooks;
the master/tenant bases (``master/repository.py``, ``tenant/repository.py``)
pin which database the session speaks to at the type level.
"""

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession


class CrudRepository[EntityT, KeyT, ModelT](ABC):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @abstractmethod
    def _key(self, entity: EntityT) -> KeyT:
        """The identity the aggregate declares in domain (``Entity[TKey].id``)."""

    @abstractmethod
    def _to_entity(self, row: ModelT) -> EntityT: ...

    @abstractmethod
    def _to_model(self, entity: EntityT) -> ModelT: ...

    @abstractmethod
    def _apply(self, row: ModelT, entity: EntityT) -> None:
        """Copy *entity*'s mutable fields onto the persisted row."""

    async def get(self, key: KeyT) -> EntityT | None:
        row = await self._session.get(self.model, key)
        return self._to_entity(row) if row is not None else None

    async def add(self, entity: EntityT) -> None:
        self._session.add(self._to_model(entity))
        # The models declare no relationship(), so the session has no mapper
        # dependency to order INSERTs by and would emit a row before the one
        # its foreign key references. Flushing here pins insertion order;
        # committing stays with the UnitOfWork.
        await self._session.flush()

    async def update(self, entity: EntityT) -> None:
        key = self._key(entity)
        row = await self._session.get(self.model, key)
        if row is None:
            raise LookupError(f"{self.model.__name__} {key} not persisted")
        self._apply(row, entity)
