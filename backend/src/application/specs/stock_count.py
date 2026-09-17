"""The reads the stock-count use cases need, one class each.

Written against ``StockCountModel``, not ``StockCount`` (ADR 0007). Every
spec eager-loads both child collections and each one's ``product`` — a
line's is never null (FR-6.2 always names a catalog row), a unit's is
nullable (a surprise IMEI names none until priced, FR-6.4b).
"""

from uuid import UUID

from sqlalchemy.orm import selectinload

from application.common.specification import Specification
from domain.enums import DocumentStatus
from infrastructure.persistence.tenant.models import (
    StockCountLineModel,
    StockCountModel,
    StockCountUnitModel,
)

_WITH_CHILDREN = (
    selectinload(StockCountModel.units).selectinload(StockCountUnitModel.product),
    selectinload(StockCountModel.lines).selectinload(StockCountLineModel.product),
)


class StockCountById(Specification[StockCountModel]):
    """Read-only: no lock. For the reads that only display a count."""

    def __init__(self, stock_count_id: UUID) -> None:
        super().__init__(StockCountModel)
        self.stock_count_id = stock_count_id
        self.where(StockCountModel.id == stock_count_id)
        self.include(*_WITH_CHILDREN)


class StockCountForWrite(Specification[StockCountModel]):
    """The specification a command uses to load a count it will mutate.

    Scanning, counting, closing, confirming and cancelling all load through
    this: it locks ``stock_counts`` and brings both child collections so
    the mapper can sync them.
    """

    def __init__(self, stock_count_id: UUID) -> None:
        super().__init__(StockCountModel)
        self.stock_count_id = stock_count_id
        self.where(StockCountModel.id == stock_count_id)
        self.include(*_WITH_CHILDREN)
        self.lock()


class StockCountBrowse(Specification[StockCountModel]):
    """The count list: number substring match, optional status and
    location filters, newest first with ``id`` as the tie-break."""

    def __init__(
        self,
        search: str | None = None,
        status: DocumentStatus | None = None,
        location_id: UUID | None = None,
    ) -> None:
        super().__init__(StockCountModel)
        self.search = search
        self.status = status
        self.location_id = location_id
        if search:
            self.where(StockCountModel.number.ilike(f"%{search.strip()}%"))
        if status is not None:
            self.where(StockCountModel.status == status.value)
        if location_id is not None:
            self.where(StockCountModel.location_id == location_id)
        self.include(*_WITH_CHILDREN)
        self.order(StockCountModel.created_at.desc(), StockCountModel.id)
