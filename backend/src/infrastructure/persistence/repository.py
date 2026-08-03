"""The two roots every repository starts from.

``SqlRepository`` is the mechanics: a session, one insert, and the reads —
each read taking the mapping function to apply, so a statement that selects
two things is not a different *kind* of repository. It states no rule and
declares no hook.

``CrudRepository`` adds the CRUD template for the aggregates whose whole
persisted state is one row, which is most of them. It is a **convenience
for the majority, not a classification of tables**: an aggregate that does
not fit inherits ``SqlRepository`` (through ``MasterRepository`` /
``TenantRepository``) and writes the two or three methods its port declares.
It does not get a base of its own — that is what turned four bases into a
taxonomy nothing could be added to.

The type parameters that pin a database live on the master/tenant
subclasses (``master/repositories/base.py``, ``tenant/repositories/base.py``).
"""

from abc import ABC, abstractmethod
from collections.abc import Callable

from sqlalchemy import ColumnExpressionArgument, Row, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.core import Entity


class SqlRepository:
    """A session and the reads/writes that do not depend on any table's shape.

    Every helper is generic **per method**, not per class, and takes the
    row → entity mapping as an argument. That is the whole reason a joined
    read needs no separate base: ``_one``/``_many`` bind one model,
    ``_one_row``/``_many_rows`` bind a whole select tuple, and both live
    side by side on the same class.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _insert(self, row: object) -> None:
        self._session.add(row)
        # The models declare no relationship(), so the session has no mapper
        # dependency to order INSERTs by and would emit a row before the one
        # its foreign key references. Flushing here pins insertion order;
        # committing stays with the UnitOfWork.
        await self._session.flush()

    async def _row[ModelT](self, model: type[ModelT], key: object) -> ModelT | None:
        """The persisted row itself, for the callers that must mutate it."""
        return await self._session.get(model, key)

    async def _require_row[ModelT](self, model: type[ModelT], key: object) -> ModelT:
        """As ``_row``, for an update: absent is a programming error.

        Every ``update`` here loads the row to copy fields onto, so every
        one of them needs the same "and if it is not there?" answer. Asked
        once, the answer cannot drift into three wordings of the same
        failure.
        """
        row = await self._row(model, key)
        if row is None:
            raise LookupError(f"{model.__name__} {key} not persisted")
        return row

    async def _one[ModelT, EntityT](
        self, stmt: Select[tuple[ModelT]], hydrate: Callable[[ModelT], EntityT]
    ) -> EntityT | None:
        row = await self._session.scalar(stmt)
        return None if row is None else hydrate(row)

    async def _many[ModelT, EntityT](
        self, stmt: Select[tuple[ModelT]], hydrate: Callable[[ModelT], EntityT]
    ) -> list[EntityT]:
        rows = await self._session.scalars(stmt)
        return [hydrate(row) for row in rows]

    async def _one_row[*Ts, EntityT](
        self, stmt: Select[tuple[*Ts]], hydrate: Callable[[Row[tuple[*Ts]]], EntityT]
    ) -> EntityT | None:
        """As ``_one``, for a statement that selects more than the model.

        An entity whose amounts are denominated by a row it points at
        (§4.5 rule 3) is rebuilt from the join, not from its own row —
        ``device_units`` and the two price logs all read this way.

        *hydrate* unpacks with ``row._tuple()``: SQLAlchemy underscores its
        whole ``Row`` API deliberately, so that a selected column named
        ``count`` or ``keys`` can never shadow a method. The underscore
        marks the supported accessor here, not a private one.
        """
        found = (await self._session.execute(stmt)).first()
        return None if found is None else hydrate(found)

    async def _many_rows[*Ts, EntityT](
        self, stmt: Select[tuple[*Ts]], hydrate: Callable[[Row[tuple[*Ts]]], EntityT]
    ) -> list[EntityT]:
        rows = await self._session.execute(stmt)
        return [hydrate(row) for row in rows]

    async def _page[ModelT, EntityT](
        self,
        stmt: Select[tuple[ModelT]],
        page: int,
        page_size: int,
        hydrate: Callable[[ModelT], EntityT],
    ) -> tuple[list[EntityT], int]:
        """One page of *stmt* plus the count it would have returned unpaged.

        The count runs over ``stmt`` as a subquery rather than a rebuilt
        query, so a filter can never be applied to the rows and forgotten
        on the total. *stmt* must already carry its ``ORDER BY`` — without
        one, "page 2" is not a stable concept.
        """
        total = await self._session.scalar(select(func.count()).select_from(stmt.subquery()))
        items = await self._many(stmt.offset((page - 1) * page_size).limit(page_size), hydrate)
        return items, total or 0


# The bound is the unsubscripted ``Entity``, not ``Entity[KeyT]``: a bound
# may not reference another type parameter ("TypeVar constraint type cannot
# be generic"). Binding to the base class is enough to give ``update`` an
# ``id`` to look the row up by; ``KeyT`` still pins what that id is at
# each subclass.
class CrudRepository[EntityT: Entity, KeyT, ModelT](SqlRepository, ABC):
    """The CRUD template for an aggregate whose persisted state is one row.

    ``ModelT`` is a single model on purpose, and that is exactly the limit
    of this class: an aggregate spread over several tables — a document and
    its lines, a unit priced by its product — cannot honour these hooks and
    should not try. It inherits ``SqlRepository`` instead.
    """

    model: type[ModelT]

    @abstractmethod
    def _to_entity(self, row: ModelT) -> EntityT: ...

    @abstractmethod
    def _to_model(self, entity: EntityT) -> ModelT: ...

    @abstractmethod
    def _apply(self, row: ModelT, entity: EntityT) -> None:
        """Copy *entity*'s mutable fields onto the persisted row."""

    async def get(self, key: KeyT) -> EntityT | None:
        row = await self._row(self.model, key)
        return self._to_entity(row) if row is not None else None

    async def add(self, entity: EntityT) -> None:
        await self._insert(self._to_model(entity))

    async def update(self, entity: EntityT) -> None:
        row = await self._require_row(self.model, entity.id)
        self._apply(row, entity)

    async def _find_one(self, *criteria: ColumnExpressionArgument[bool]) -> EntityT | None:
        """The single row matching *criteria*, as an entity.

        The lookups that are not by primary key (by SKU, by email, by slug)
        all reduce to this; routing them through one place is what stops a
        new finder from forgetting ``_to_entity`` and leaking a row.
        """
        return await self._one(select(self.model).where(*criteria), self._to_entity)

    async def _find_many(self, stmt: Select[tuple[ModelT]]) -> list[EntityT]:
        return await self._many(stmt, self._to_entity)
