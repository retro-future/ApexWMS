"""The database-agnostic repository generics (ADR 0007).

``SqlAppendOnlyRepository`` is ``add`` plus the spec reads and nothing else
— the ledgers and logs reach it, and it has no ``update``/``delete`` on
purpose (§4.3 rule 2). ``SqlAlchemyRepository`` extends it with the write
side an aggregate needs. Both take a ``Specification`` and a per-aggregate
mapper.

The type parameters that pin a database live on the ``tenant``/``master``
subclasses in this package.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from application.common.mapper import EntityMapper
from application.common.specification import Specification
from application.errors import EntityNotPersistedError
from domain.core import Entity


class SqlAppendOnlyRepository[TEntity: Entity, TModel: DeclarativeBase]:
    """``add`` plus spec reads. No ``update``, no ``delete``: a ledger row
    goes in and is never touched again (§4.3 rule 2, §4.5b). The rule is
    the *absence* of the methods, so a handler that tries to edit history
    fails to type-check.

    Stateless by design — session, model class, mapper, nothing else.
    """

    def __init__(
        self,
        session: AsyncSession,
        model_cls: type[TModel],
        mapper: EntityMapper[TEntity, TModel],
    ) -> None:
        self._session = session
        self._model_cls = model_cls
        self._mapper = mapper

    def _apply(self, spec: Specification[TModel]) -> Select[tuple[TModel]]:
        stmt = select(self._model_cls)
        for target in spec.joins:
            stmt = stmt.join(target)
        if spec.criteria:
            stmt = stmt.where(*spec.criteria)
        if spec.options:
            stmt = stmt.options(*spec.options)
        if spec.order_by:
            stmt = stmt.order_by(*spec.order_by)
        if spec.offset is not None:
            stmt = stmt.offset(spec.offset)
        if spec.limit is not None:
            stmt = stmt.limit(spec.limit)
        if spec.for_update:
            stmt = stmt.with_for_update()
        return stmt

    async def find(self, spec: Specification[TModel]) -> Sequence[TEntity]:
        rows = await self._session.scalars(self._apply(spec))
        # unique() is mandatory: a joined eager load on a collection yields
        # one row per child, and the parent repeated alongside each of them.
        return [self._mapper.to_entity(row) for row in rows.unique().all()]

    async def find_one(self, spec: Specification[TModel]) -> TEntity | None:
        rows = await self._session.scalars(self._apply(spec).limit(1))
        row = rows.unique().one_or_none()
        return None if row is None else self._mapper.to_entity(row)

    async def count(self, spec: Specification[TModel]) -> int:
        """The unpaged total: *spec*'s limit, offset and ordering are ignored."""
        stmt = select(func.count()).select_from(self._model_cls)
        for target in spec.joins:
            stmt = stmt.join(target)
        if spec.criteria:
            stmt = stmt.where(*spec.criteria)
        return await self._session.scalar(stmt) or 0

    async def get(self, entity_id: Any) -> TEntity | None:
        """Load by primary key, no lock and no eager loading (see the port)."""
        row = await self._session.get(self._model_cls, entity_id)
        return None if row is None else self._mapper.to_entity(row)

    async def add(self, entity: TEntity) -> None:
        self._session.add(self._mapper.to_model(entity))


class SqlAlchemyRepository[TEntity: Entity, TModel: DeclarativeBase](
    SqlAppendOnlyRepository[TEntity, TModel]
):
    """The append-only reads plus the write side an aggregate needs:
    ``exists``, ``update``, ``delete``.

    Stateless by design — no identity map and no dirty set: the SQLAlchemy
    session already is one, and a second on top of it is how two answers to
    "what is the current state of this row" start to disagree.
    """

    async def exists(self, spec: Specification[TModel]) -> bool:
        return await self.count(spec) > 0

    async def update(
        self, entity: TEntity, spec: Specification[TModel] | None = None
    ) -> None:
        # Without a spec: the row is normally still in the session's
        # identity map from the handler's own load. With one: the mapper's
        # write path reads a relationship, so re-load through the spec that
        # eager-loads (and locks) it rather than a bare get() that would
        # hand back a row with the collection unloaded.
        if spec is None:
            row = await self._session.get(self._model_cls, entity.id)
        else:
            rows = await self._session.scalars(self._apply(spec).limit(1))
            row = rows.unique().one_or_none()
        if row is None:
            raise EntityNotPersistedError(self._model_cls.__name__, entity.id)
        self._mapper.to_model(entity, row)

    async def delete(self, entity: TEntity) -> None:
        row = await self._session.get(self._model_cls, entity.id)
        if row is not None:
            await self._session.delete(row)
