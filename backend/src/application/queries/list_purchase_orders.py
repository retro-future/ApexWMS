"""What the store has on order.

Each row carries its own fulfilment state, so the outstanding-orders
screen is one request rather than one per order.
"""

from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import PurchaseOrderData
from application.ports import GoodsReceiptRepository, PurchaseOrderRepository
from domain.enums import DocumentStatus


class ListPurchaseOrdersQuery(PagedQuery[PagedResult[PurchaseOrderData]]):
    search: str | None = None
    status: DocumentStatus | None = None
    supplier_id: UUID | None = None


class ListPurchaseOrdersHandler(
    IRequestHandler[PagedResult[PurchaseOrderData], ListPurchaseOrdersQuery]
):
    def __init__(
        self, orders: PurchaseOrderRepository, receipts: GoodsReceiptRepository
    ) -> None:
        self._orders = orders
        self._receipts = receipts

    async def handle(
        self, request: ListPurchaseOrdersQuery
    ) -> PagedResult[PurchaseOrderData]:
        orders, total = await self._orders.list_page(
            page=request.page,
            page_size=request.page_size,
            search=request.search,
            status=request.status,
            supplier_id=request.supplier_id,
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
