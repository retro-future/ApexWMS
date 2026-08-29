"""The repository port command handlers depend on.

Query variability lives in the ``Specification`` a caller passes in, not in
a method name the port has to grow. Returns domain entities, never ORM
models.

``delete`` is here because the port's shape is fixed. Nothing in this
system calls it: records transition state via ``update`` (revoked,
accepted, deactivated), and the ledgers are append-only (PRD §2).

``MasterDbRepository``/``TenantDbRepository`` add nothing to the shape.
They exist so the two databases have two distinct DI keys, the same reason
``MasterUnitOfWork`` and ``TenantUnitOfWork`` are separate ports (PRD
§3.1): one generic factory per database, each holding the session type its
side of the split is allowed to touch. A handler names the one it means, so
"which database does this read hit" is answered by the constructor
signature rather than by whatever the container happened to wire.

Named for the *database*, not the entity: the port for the tenant-registry
aggregate would otherwise be a ``TenantRepository`` that is nothing to do
with which database a call reaches.
"""

from collections.abc import Sequence
from typing import Any, Protocol

from application.common.specification import Specification


class Repository[TEntity, TModel](Protocol):
    async def find(self, spec: Specification[TModel]) -> Sequence[TEntity]: ...

    async def find_one(self, spec: Specification[TModel]) -> TEntity | None: ...

    async def get(self, entity_id: Any) -> TEntity | None:
        """Load by primary key: the no-lock read a query handler needs.

        No eager loading — an aggregate whose mapper walks a collection is
        loaded through a ``Specification`` that ``selectinload``s it, not
        through here.
        """
        ...

    async def count(self, spec: Specification[TModel]) -> int: ...

    async def exists(self, spec: Specification[TModel]) -> bool: ...

    async def add(self, entity: TEntity) -> None: ...

    async def update(
        self, entity: TEntity, spec: Specification[TModel] | None = None
    ) -> None:
        """Persist *entity*'s changes.

        Pass *spec* when the mapper's write path reads a relationship (a
        document that syncs its lines): the persistent row is re-loaded
        through it, so the collection is present and locked. A flat
        aggregate omits it and the row comes straight from the identity
        map.
        """
        ...

    async def delete(self, entity: TEntity) -> None: ...


class MasterDbRepository[TEntity, TModel](Repository[TEntity, TModel], Protocol):
    """The platform's database: the tenant registry and platform identity."""


class TenantDbRepository[TEntity, TModel](Repository[TEntity, TModel], Protocol):
    """One store's database. No method takes a tenant id — the session is
    the tenant, so there is no filter to forget."""


class AppendOnlyDbRepository[TEntity, TModel](Protocol):
    """``add`` plus the spec reads, and nothing else. The ledgers and logs
    depend on this: a row goes in and is never touched again (§4.3 rule 2),
    so ``update``/``delete`` are *absent*, not raising — a handler that
    tries to edit history fails to type-check.

    A projection read (a total, a bucket, a bare id list) is not a spec
    read; it goes in a query service (`query-services.md`)."""

    async def add(self, entity: TEntity) -> None: ...

    async def get(self, entity_id: Any) -> TEntity | None: ...

    async def find(self, spec: Specification[TModel]) -> Sequence[TEntity]: ...

    async def find_one(self, spec: Specification[TModel]) -> TEntity | None: ...

    async def count(self, spec: Specification[TModel]) -> int: ...


class TenantAppendOnlyRepository[TEntity, TModel](
    AppendOnlyDbRepository[TEntity, TModel], Protocol
):
    """One store's ledger or log. Its own DI key, the same reason
    ``TenantDbRepository`` has one."""
