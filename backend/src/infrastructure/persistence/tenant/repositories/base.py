"""The TenantDB repository bases.

The constructor demands ``TenantSession`` — see ``master/repositories/base.py``
for the rationale.

Four bases, because a store's tables come in four shapes:

- ``TenantRowRepository`` — records read and edited whose entity can be
  rebuilt from their own row: ``stock_levels``.
- ``TenantCrudRepository`` — the subset of those that are *browsable*,
  which is what ``ActivatableRow`` buys: the identity records and the M2
  catalog, all paged the same way.
- ``TenantJoinedRepository`` — records whose entity **cannot** be rebuilt
  from their own row, because their amounts are denominated by a product
  they point at (§4.5 rule 3): ``device_units``.
- ``TenantLedgerRepository`` — the ones only ever *appended to*: the price
  logs and, from M3, the stock and financial ledgers.

The last two share their constructor and ``add`` — ``TenantJoinedRepository``
inherits ``TenantLedgerRepository`` for that machinery, not because
``device_units`` is a ledger, and adds ``update`` on top, which is exactly
the difference between a record and a ledger row.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import InstrumentedAttribute

from domain.core import Entity
from infrastructure.persistence.repository import CrudRepository
from infrastructure.persistence.tenant.models.base import ActivatableRow
from infrastructure.types import TenantSession


class TenantRowRepository[EntityT: Entity, KeyT, ModelT](
    CrudRepository[EntityT, KeyT, ModelT], ABC
):
    """CRUD against *this tenant's* database, and nothing more.

    The narrowed constructor is the whole point: a ``MasterSession`` is a
    type error here, so the container physically cannot hand a store's
    repository the platform's database. ``ty`` is the only thing that
    enforces it — a ``NewType`` is an identity function at runtime — which
    is why a red type check is a broken build.
    """

    def __init__(self, session: TenantSession) -> None:
        super().__init__(session)


class TenantCrudRepository[EntityT: Entity, KeyT, ModelT: ActivatableRow](
    TenantRowRepository[EntityT, KeyT, ModelT], ABC
):
    """A tenant record that also carries ``is_active``/``created_at``, and
    so can be browsed by the one paging shape every catalog list shares."""

    async def _browse_page(
        self,
        page: int,
        page_size: int,
        search: str | None,
        is_active: bool | None,
        *search_columns: InstrumentedAttribute[str] | InstrumentedAttribute[str | None],
        stmt: Select[tuple[ModelT]] | None = None,
    ) -> tuple[list[EntityT], int]:
        """The browse shape every catalog list endpoint shares (FR-2.x).

        A case-insensitive substring match over *search_columns*, an
        optional active/inactive filter, oldest first — the latter two
        columns come from the ``ActivatableRow`` bound on ``ModelT``.

        Aggregate-specific filters go on *stmt* before the call — that
        keeps "which columns does search cover" declarative here while
        leaving anything genuinely per-aggregate visible at its call site.
        """
        stmt = select(self.model) if stmt is None else stmt
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(or_(*(column.ilike(term) for column in search_columns)))
        if is_active is not None:
            stmt = stmt.where(self.model.is_active.is_(is_active))
        return await self._page(stmt.order_by(self.model.created_at), page, page_size)


class TenantLedgerRepository[EntityT: Entity, ModelT](ABC):
    """The base for append-only tenant tables (PRD §4.3 rule 2, §4.5b).

    There is no ``update``, and no ``_apply`` hook with which to write one.
    A ledger row is never edited — a mistake is corrected by appending its
    compensation — so the *absence* of the method is the rule, stated in
    the type rather than in a code review.

    Also the insert/read machinery ``TenantJoinedRepository`` reuses — that
    class is not itself a ledger, it just starts from the same constructor
    and ``add``, and adds ``update`` on top for the one aggregate
    (``device_units``) that needs both a joined hydration *and* to be
    editable.
    """

    model: type[ModelT]

    def __init__(self, session: TenantSession) -> None:
        self._session = session

    @abstractmethod
    def _to_model(self, entity: EntityT) -> ModelT: ...

    async def add(self, entity: EntityT) -> None:
        self._session.add(self._to_model(entity))
        # Same reason as ``CrudRepository.add``: no relationship() means no
        # mapper-ordered INSERTs, and these rows' foreign keys must land
        # after the rows they point at. Committing stays with the UnitOfWork.
        await self._session.flush()

    async def _find_many(
        self, stmt: Select[tuple[ModelT]], hydrate: Callable[[ModelT], EntityT]
    ) -> list[EntityT]:
        """The read every plain (non-priced) ledger table shares.

        *hydrate* is passed in rather than assumed as a ``self._to_entity``
        override, so this stays usable by every ``TenantLedgerRepository``
        subclass without forcing one on the two price-log repositories,
        which hydrate with an extra joined currency column instead.
        """
        rows = await self._session.scalars(stmt)
        return [hydrate(row) for row in rows]


class TenantJoinedRepository[EntityT: Entity, KeyT, ModelT](
    TenantLedgerRepository[EntityT, ModelT], ABC
):
    """A record whose entity cannot be rebuilt from its own row alone.

    ``device_units`` is the case this exists for. A unit's cost and asking
    price are bare minor amounts denominated by the *product's* currency
    (§4.5 rule 3), which the unit deliberately does not store — so it
    cannot drift from the catalog row it belongs to. Every read therefore
    joins, and ``CrudRepository``'s single-row ``_to_entity`` hook cannot
    express a mapping that needs two.
    """

    @abstractmethod
    def _apply(self, row: ModelT, entity: EntityT) -> None:
        """Copy *entity*'s mutable fields onto the persisted row."""

    async def update(self, entity: EntityT) -> None:
        row = await self._session.get(self.model, entity.id)
        if row is None:
            raise LookupError(f"{self.model.__name__} {entity.id} not persisted")
        self._apply(row, entity)
