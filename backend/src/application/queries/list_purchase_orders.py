"""What the store has on order.

Each row carries its own fulfilment state, so the outstanding-orders
screen is one request rather than one per order.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import PurchaseOrderData
from application.ports import GoodsReceiptRepository
from application.specs import PurchaseOrderBrowse
from domain.entities import PurchaseOrder
from domain.enums import DocumentStatus
from infrastructure.persistence.tenant.models import PurchaseOrderModel


class ListPurchaseOrdersQuery(PagedQuery[PagedResult[PurchaseOrderData]]):
    search: str | None = None
    status: DocumentStatus | None = None
    supplier_id: UUID | None = None


class ListPurchaseOrdersHandler(
    IRequestHandler[PagedResult[PurchaseOrderData], ListPurchaseOrdersQuery]
):
    def __init__(
        self,
        orders: TenantDbRepository[PurchaseOrder, PurchaseOrderModel],
        receipts: GoodsReceiptRepository,
    ) -> None:
        self._orders = orders
        self._receipts = receipts

    async def handle(
        self, request: ListPurchaseOrdersQuery
    ) -> PagedResult[PurchaseOrderData]:
        spec = PurchaseOrderBrowse(
            search=request.search,
            status=request.status,
            supplier_id=request.supplier_id,
        )
        total = await self._orders.count(spec)
        orders = await self._orders.find(
            spec.page(request.page, request.page_size)
        )
        data = [
            PurchaseOrderData.from_entity(
                order, await self._receipts.received_quantities(order.id)
            )
            for order in orders
        ]
        return PagedResult[PurchaseOrderData].succeed_with_data(
            data=data,
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
