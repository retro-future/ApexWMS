"""One Purchase Order, with FR-3.9's received-versus-ordered state.

``fulfilment`` is computed here rather than stored: it is a comparison of
what the order asked for against what confirmed receipts actually brought
in, and both halves are already recorded. A stored copy would be one more
projection to keep honest for no new information.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import PurchaseOrderData
from application.ports import GoodsReceiptRepository
from application.specs import PurchaseOrderById
from domain.entities import PurchaseOrder
from infrastructure.persistence.tenant.models import PurchaseOrderModel


class GetPurchaseOrderQuery(Query[ResultWithData[PurchaseOrderData]]):
    purchase_order_id: UUID


class GetPurchaseOrderHandler(
    IRequestHandler[ResultWithData[PurchaseOrderData], GetPurchaseOrderQuery]
):
    def __init__(
        self,
        orders: TenantDbRepository[PurchaseOrder, PurchaseOrderModel],
        receipts: GoodsReceiptRepository,
    ) -> None:
        self._orders = orders
        self._receipts = receipts

    async def handle(
        self, request: GetPurchaseOrderQuery
    ) -> ResultWithData[PurchaseOrderData]:
        order = await self._orders.find_one(
            PurchaseOrderById(request.purchase_order_id)
        )
        if order is None:
            raise NotFoundError(
                f"purchase order {request.purchase_order_id} does not exist in this store"
            )
        received = await self._receipts.received_quantities(order.id)
        return ResultWithData[PurchaseOrderData].succeed_with_data(
            PurchaseOrderData.from_entity(order, received)
        )
