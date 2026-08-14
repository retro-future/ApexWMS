"""FR-3.2: confirming a Purchase Order fixes its numbers.

**It does not change stock.** This is the one document whose confirm writes
nothing to either ledger — a PO is an intention to buy (§4.4), and goods
arrive later on a Goods Receipt. There is no ``LedgerPoster`` in this
handler for exactly that reason, and it is not an omission.
"""

from uuid import UUID

from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.models import PurchaseOrderData
from application.ports import (
    Clock,
    GoodsReceiptRepository,
    PurchaseOrderRepository,
    TenantUnitOfWork,
)
from application.services import DocumentLoader


class ConfirmPurchaseOrderCommand(Command[ResultWithData[PurchaseOrderData]]):
    # No body: this action needs nothing beyond the order in the URL. The
    # router builds this straight from the path, with no request model in
    # between.
    purchase_order_id: UUID


class ConfirmPurchaseOrderHandler(
    IRequestHandler[ResultWithData[PurchaseOrderData], ConfirmPurchaseOrderCommand]
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
        self, request: ConfirmPurchaseOrderCommand
    ) -> ResultWithData[PurchaseOrderData]:
        order = await self._loader.load_order(request.purchase_order_id)

        order.confirm(self._clock.now(), self._current.user_id)
        await self._orders.update(order)
        await self._uow.commit()

        received = await self._receipts.received_quantities(order.id)
        return ResultWithData[PurchaseOrderData].succeed_with_data(
            PurchaseOrderData.from_entity(order, received)
        )
