"""What has been received, and what is still being scanned.

Filterable by ``acquisition_source``, which is the point of FR-3.3b's enum:
*"what did we take in from walk-ins this month?"* is a query rather than a
filter on a supplier's name.
"""

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.dtos import CurrentUser
from application.models import GoodsReceiptData
from application.ports import GoodsReceiptRepository
from domain.enums import AcquisitionSource, DocumentStatus
from domain.permissions import Permission


class ListGoodsReceiptsQuery(PagedQuery[PagedResult[GoodsReceiptData]]):
    search: str | None = None
    status: DocumentStatus | None = None
    acquisition_source: AcquisitionSource | None = None


class ListGoodsReceiptsHandler(
    IRequestHandler[PagedResult[GoodsReceiptData], ListGoodsReceiptsQuery]
):
    def __init__(self, receipts: GoodsReceiptRepository, current: CurrentUser) -> None:
        self._receipts = receipts
        self._current = current

    async def handle(
        self, request: ListGoodsReceiptsQuery
    ) -> PagedResult[GoodsReceiptData]:
        receipts, total = await self._receipts.list_page(
            page=request.page,
            page_size=request.page_size,
            search=request.search,
            status=request.status,
            acquisition_source=request.acquisition_source,
        )
        show_cost = Permission.COST_VIEW in self._current.permissions
        return PagedResult[GoodsReceiptData].succeed_with_data(
            data=[
                GoodsReceiptData.from_entity(r, show_cost=show_cost) for r in receipts
            ],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
