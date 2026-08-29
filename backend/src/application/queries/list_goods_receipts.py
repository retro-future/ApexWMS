"""What has been received, and what is still being scanned.

Filterable by ``acquisition_source``, which is the point of FR-3.3b's enum:
*"what did we take in from walk-ins this month?"* is a query rather than a
filter on a supplier's name.
"""

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, PagedQuery, PagedResult
from application.dtos import CurrentUser
from application.models import GoodsReceiptData
from application.specs import GoodsReceiptBrowse
from domain.entities import GoodsReceipt
from domain.enums import AcquisitionSource, DocumentStatus
from domain.permissions import Permission
from infrastructure.persistence.tenant.models import GoodsReceiptModel


class ListGoodsReceiptsQuery(PagedQuery[PagedResult[GoodsReceiptData]]):
    search: str | None = None
    status: DocumentStatus | None = None
    acquisition_source: AcquisitionSource | None = None


class ListGoodsReceiptsHandler(
    IRequestHandler[PagedResult[GoodsReceiptData], ListGoodsReceiptsQuery]
):
    def __init__(
        self,
        receipts: TenantDbRepository[GoodsReceipt, GoodsReceiptModel],
        current: CurrentUser,
    ) -> None:
        self._receipts = receipts
        self._current = current

    async def handle(
        self, request: ListGoodsReceiptsQuery
    ) -> PagedResult[GoodsReceiptData]:
        spec = GoodsReceiptBrowse(
            search=request.search,
            status=request.status,
            acquisition_source=request.acquisition_source,
        )
        total = await self._receipts.count(spec)
        receipts = await self._receipts.find(spec.page(request.page, request.page_size))
        show_cost = Permission.COST_VIEW in self._current.permissions
        return PagedResult[GoodsReceiptData].succeed_with_data(
            data=[
                GoodsReceiptData.from_entity(r, show_cost=show_cost) for r in receipts
            ],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
