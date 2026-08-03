"""The TenantDB repository bases: a convenience, not a classification.

Both narrow their constructor to ``TenantSession``, which is the whole
reason they exist as separate classes at all: a ``MasterSession`` is then a
type error here, so the container physically cannot hand a store's
repository the platform's database. ``ty`` is the only thing that enforces
it — a ``NewType`` is an identity function at runtime — which is why a red
type check is a broken build.

- ``TenantCrudRepository`` — for an aggregate whose whole persisted state
  is one ``ActivatableRow``: the identity records and the M2 catalog, all
  browsable through the same paging shape.
- ``TenantRepository`` — for everything else: the two ledgers, the two
  price logs, ``device_units``, the settings row, and the documents M4
  brings. It carries no hooks and no ``get``/``add``/``update``, so a
  repository here writes exactly the methods its port declares — and
  "a ledger has no ``update``" stays true simply because nobody wrote one.

**An aggregate that does not fit ``TenantCrudRepository`` inherits
``TenantRepository``. It does not get a base of its own.** Four bases grew
here once because each misfit was answered with a new sibling, and a
hierarchy that has to classify every table is a hierarchy that must grow
with every table. The append-only rule lives in
``application/ports/repository.py``'s ``AppendOnlyRepository``, which is
what handlers actually depend on — not in a base class.
"""

from abc import ABC

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import InstrumentedAttribute

from domain.core import Entity
from infrastructure.persistence.repository import CrudRepository, SqlRepository
from infrastructure.persistence.tenant.models.base import ActivatableRow
from infrastructure.types import TenantSession


class TenantRepository(SqlRepository):
    """Reads and writes against *this tenant's* database, and nothing more."""

    def __init__(self, session: TenantSession) -> None:
        super().__init__(session)


class TenantCrudRepository[EntityT: Entity, KeyT, ModelT: ActivatableRow](
    CrudRepository[EntityT, KeyT, ModelT], ABC
):
    """A one-row tenant record that also carries ``is_active``/``created_at``,
    and so can be browsed by the one paging shape every catalog list shares."""

    def __init__(self, session: TenantSession) -> None:
        super().__init__(session)

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
        optional active/inactive filter, oldest first — the ordering and
        filter columns come from the ``ActivatableRow`` bound on ``ModelT``.

        The tie-break on ``id`` is what makes the order *total*: rows
        created inside the same clock tick (a seeding run, a coarse
        platform clock) would otherwise sort arbitrarily, and two
        arbitrary sorts of the same table can show one row on both pages
        and another on neither.

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
        return await self._page(
            stmt.order_by(self.model.created_at, self.model.id),
            page,
            page_size,
            self._to_entity,
        )
