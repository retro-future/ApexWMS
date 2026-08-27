"""FR-9.5: the raw stock ledger, filterable.

The report with no opinion. Every other one in §5.9 answers a question the
owner already has; this one exists for the question nobody anticipated, so
its filters compose and it excludes nothing — a reversal appears beside the
movement it reverses, because both happened.
"""

from datetime import datetime
from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import MovementRowData
from application.ports import StockMovementRepository
from domain.enums import MovementType


class ListMovementsQuery(PagedQuery[PagedResult[MovementRowData]]):
    product_id: UUID | None = None
    location_id: UUID | None = None
    device_unit_id: UUID | None = None
    user_id: UUID | None = None
    movement_type: MovementType | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None


class ListMovementsHandler(
    IRequestHandler[PagedResult[MovementRowData], ListMovementsQuery]
):
    def __init__(self, movements: StockMovementRepository) -> None:
        self._movements = movements

    async def handle(self, request: ListMovementsQuery) -> PagedResult[MovementRowData]:
        rows, total = await self._movements.list_page(
            page=request.page,
            page_size=request.page_size,
            product_id=request.product_id,
            location_id=request.location_id,
            device_unit_id=request.device_unit_id,
            user_id=request.user_id,
            movement_type=request.movement_type,
            from_date=request.from_date,
            to_date=request.to_date,
        )
        return PagedResult[MovementRowData].succeed_with_data(
            data=[MovementRowData.from_entity(row) for row in rows],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
