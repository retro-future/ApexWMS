"""The TenantDB repository base.

The constructor demands ``TenantSession`` — see ``master/repositories/base.py``
for the rationale. The subclasses are the tenant's own identity records
plus the M2 catalog aggregates.
"""

from abc import ABC

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import InstrumentedAttribute

from domain.core import Entity
from infrastructure.persistence.repository import CrudRepository
from infrastructure.persistence.tenant.models.base import ActivatableRow
from infrastructure.types import TenantSession


class TenantCrudRepository[EntityT: Entity, KeyT, ModelT: ActivatableRow](
    CrudRepository[EntityT, KeyT, ModelT], ABC
):
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
