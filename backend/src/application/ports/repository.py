"""The named-method repository ports the unconverted aggregates still use.

The port every aggregate is moving to is ``application/common/repository.py``
— filters live in a ``Specification`` there, not in a method name. These
two disappear as each aggregate converts.
"""

from typing import Protocol


class LegacyRepository[EntityT, KeyT](Protocol):
    """The pre-specification port: one aggregate, one key type.

    ``KeyT`` is the identity the aggregate declares in domain
    (``Entity[TKey].id``), so lookups and updates are typed end to end.
    Per-aggregate ports in ``master/`` and ``tenant/`` extend this with the
    queries that have no generic shape — which is the growth this port is
    being retired to stop.
    """

    async def get(self, key: KeyT) -> EntityT | None: ...

    async def add(self, entity: EntityT) -> None: ...

    async def update(self, entity: EntityT) -> None: ...


class AppendOnlyRepository[EntityT](Protocol):
    """The port for a ledger or a log: rows go in and are never touched again.

    ``update`` is absent rather than raising, so a handler that tries to
    edit history fails to type-check instead of failing at runtime — the
    append-only rule of §4.3 and §4.5b, made structural. There is no
    ``get`` either: nothing looks a ledger row up by its own id, because
    the questions asked of these tables are always "everything for this
    product / handset / document, in order".

    Each concrete port supplies those reads; this base supplies the only
    write there is.
    """

    async def add(self, entity: EntityT) -> None: ...
