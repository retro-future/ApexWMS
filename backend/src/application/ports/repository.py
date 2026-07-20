"""The generic repository port: one aggregate, one key type.

``KeyT`` is the identity the aggregate declares in domain —
``Entity[TKey].id`` for id-keyed aggregates, ``MembershipKey`` for the
composite one — so lookups and updates are typed end to end.

Per-aggregate ports in ``master/`` and ``tenant/`` extend this with the
queries that have no generic shape. There is deliberately no ``delete``:
nothing in this system hard-deletes — records transition state via
``update`` (revoked, accepted, deactivated), and the M3+ ledgers are
append-only (PRD §2).
"""

from typing import Protocol


class Repository[EntityT, KeyT](Protocol):
    async def get(self, key: KeyT) -> EntityT | None: ...

    async def add(self, entity: EntityT) -> None: ...

    async def update(self, entity: EntityT) -> None: ...
