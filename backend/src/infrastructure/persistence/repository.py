"""The generic CRUD template implementing ``Repository[EntityT, KeyT]``.

Concrete repositories supply the row ↔ entity mapping through the hooks;
the master/tenant bases (``master/repository.py``, ``tenant/repository.py``)
pin which database the session speaks to at the type level.
"""

from abc import ABC, abstractmethod

from sqlalchemy import ColumnExpressionArgument, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.core import Entity


# The bound is the unsubscripted ``Entity``, not ``Entity[KeyT]``: a bound
# may not reference another type parameter ("TypeVar constraint type cannot
# be generic"). Binding to the base class is enough to give ``_key`` an
# ``id`` to return; ``KeyT`` still pins what that id is at each subclass.
class CrudRepository[EntityT: Entity, KeyT, ModelT](ABC):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _key(self, entity: EntityT) -> KeyT:
        """The identity the aggregate declares in domain (``Entity[TKey].id``)."""
        return entity.id

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

    async def _find_one(self, *criteria: ColumnExpressionArgument[bool]) -> EntityT | None:
        """The single row matching *criteria*, as an entity.

        The lookups that are not by primary key (by SKU, by email, by slug)
        all reduce to this; routing them through one place is what stops a
        new finder from forgetting ``_to_entity`` and leaking a row.
        """
        row = await self._session.scalar(select(self.model).where(*criteria))
        return self._to_entity(row) if row is not None else None

    async def _find_many(self, stmt: Select[tuple[ModelT]]) -> list[EntityT]:
        rows = await self._session.scalars(stmt)
        return [self._to_entity(row) for row in rows]

    async def _page(
        self, stmt: Select[tuple[ModelT]], page: int, page_size: int
    ) -> tuple[list[EntityT], int]:
        """One page of *stmt* plus the count it would have returned unpaged.

        The count runs over ``stmt`` as a subquery rather than a rebuilt
        query, so a filter can never be applied to the rows and forgotten
        on the total. *stmt* must already carry its ``ORDER BY`` — without
        one, "page 2" is not a stable concept.
        """
        total = await self._session.scalar(select(func.count()).select_from(stmt.subquery()))
        items = await self._find_many(stmt.offset((page - 1) * page_size).limit(page_size))
        return items, total or 0
