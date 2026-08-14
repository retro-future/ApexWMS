"""Cancelling a confirmed Purchase Order (§4.4).

No compensation to write: confirming the order moved neither goods nor
money, so cancelling it un-moves nothing. What the state change buys is
the record that the order was called off rather than quietly forgotten,
and a fulfilment figure that stops counting it as outstanding.
"""

from uuid import UUID

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.models import PurchaseOrderData
from application.ports import (
    Clock,
    GoodsReceiptRepository,
    PurchaseOrderRepository,
    TenantUnitOfWork,
)
from application.services import DocumentLoader


class CancelPurchaseOrderCommandPayload(CamelModel):
    reason: str | None = None


class CancelPurchaseOrderCommand(
    CancelPurchaseOrderCommandPayload, Command[ResultWithData[PurchaseOrderData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    purchase_order_id: UUID


class CancelPurchaseOrderHandler(
    IRequestHandler[ResultWithData[PurchaseOrderData], CancelPurchaseOrderCommand]
):
    def __init__(
        self,
        orders: PurchaseOrderRepository,
        receipts: GoodsReceiptRepository,
        loader: DocumentLoader,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._orders = orders
        self._receipts = receipts
        self._loader = loader
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CancelPurchaseOrderCommand
    ) -> ResultWithData[PurchaseOrderData]:
        order = await self._loader.load_order(request.purchase_order_id)

        order.cancel(self._clock.now(), self._current.user_id, request.reason)
        await self._orders.update(order)
        await self._uow.commit()

        received = await self._receipts.received_quantities(order.id)
        return ResultWithData[PurchaseOrderData].succeed_with_data(
            PurchaseOrderData.from_entity(order, received)
        )
