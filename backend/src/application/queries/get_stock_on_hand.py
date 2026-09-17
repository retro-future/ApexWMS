"""FR-9.1: what the store is holding, by location, by product or by brand.

Paged after the fact rather than in SQL: an aggregate has to be complete
before it can be sliced, and the accessory half is a ledger replay per pair
(§4.6) that no ``LIMIT`` could skip. Group counts are small, so this is the
honest shape rather than a fast wrong one.
"""

from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.dtos import CurrentUser, StockGroupBy
from application.models import StockOnHandData
from application.services import StockOnHandReader
from domain.enums import TrackingType
from domain.permissions import Permission


class GetStockOnHandQuery(PagedQuery[PagedResult[StockOnHandData]]):
    group_by: StockGroupBy = StockGroupBy.LOCATION
    location_id: UUID | None = None
    product_id: UUID | None = None
    brand: str | None = None
    tracking_type: TrackingType | None = None
    out_of_stock_only: bool = False


class GetStockOnHandHandler(
    IRequestHandler[PagedResult[StockOnHandData], GetStockOnHandQuery]
):
    def __init__(self, stock: StockOnHandReader, current: CurrentUser) -> None:
        self._stock = stock
        self._current = current

    async def handle(self, request: GetStockOnHandQuery) -> PagedResult[StockOnHandData]:
        groups = await self._stock.read(
            request.group_by,
            location_id=request.location_id,
            product_id=request.product_id,
            brand=request.brand,
            tracking_type=request.tracking_type,
            out_of_stock_only=request.out_of_stock_only,
        )
        start = (request.page - 1) * request.page_size
        show_cost = Permission.COST_VIEW in self._current.permissions
        return PagedResult[StockOnHandData].succeed_with_data(
            data=[
                StockOnHandData.from_entity(group, show_cost=show_cost)
                for group in groups[start : start + request.page_size]
            ],
            page_index=request.page,
            page_size=request.page_size,
            items_count=len(groups),
        )
