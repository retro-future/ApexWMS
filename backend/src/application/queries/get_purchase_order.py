"""One Purchase Order, with FR-3.9's received-versus-ordered state.

``fulfilment`` is computed here rather than stored: it is a comparison of
what the order asked for against what confirmed receipts actually brought
in, and both halves are already recorded. A stored copy would be one more
projection to keep honest for no new information.
"""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.models import PurchaseOrderData
from application.ports import GoodsReceiptRepository
from application.services import DocumentLoader


class GetPurchaseOrderQuery(Query[ResultWithData[PurchaseOrderData]]):
    purchase_order_id: UUID


class GetPurchaseOrderHandler(
    IRequestHandler[ResultWithData[PurchaseOrderData], GetPurchaseOrderQuery]
):
    def __init__(self, loader: DocumentLoader, receipts: GoodsReceiptRepository) -> None:
        self._loader = loader
        self._receipts = receipts

    async def handle(
        self, request: GetPurchaseOrderQuery
    ) -> ResultWithData[PurchaseOrderData]:
        order = await self._loader.load_order(request.purchase_order_id)
        received = await self._receipts.received_quantities(order.id)
        return ResultWithData[PurchaseOrderData].succeed_with_data(
            PurchaseOrderData.from_entity(order, received)
        )
