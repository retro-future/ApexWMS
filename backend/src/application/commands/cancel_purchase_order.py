"""Cancelling a confirmed Purchase Order (§4.4).

No compensation to write: confirming the order moved neither goods nor
money, so cancelling it un-moves nothing. What the state change buys is
the record that the order was called off rather than quietly forgotten,
and a fulfilment figure that stops counting it as outstanding.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import PurchaseOrderData
from application.ports import (
    Clock,
    GoodsReceiptRepository,
    TenantUnitOfWork,
)
from application.specs import PurchaseOrderForWrite
from domain.entities import PurchaseOrder
from infrastructure.persistence.tenant.models import PurchaseOrderModel


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
        orders: TenantDbRepository[PurchaseOrder, PurchaseOrderModel],
        receipts: GoodsReceiptRepository,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._orders = orders
        self._receipts = receipts
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CancelPurchaseOrderCommand
    ) -> ResultWithData[PurchaseOrderData]:
        spec = PurchaseOrderForWrite(request.purchase_order_id)
        order = await self._orders.find_one(spec)
        if order is None:
            raise NotFoundError(
                f"purchase order {request.purchase_order_id} does not exist in this store"
            )

        order.cancel(self._clock.now(), self._current.user_id, request.reason)
        await self._orders.update(order, spec)
        await self._uow.commit()

        received = await self._receipts.received_quantities(order.id)
        return ResultWithData[PurchaseOrderData].succeed_with_data(
            PurchaseOrderData.from_entity(order, received)
        )
