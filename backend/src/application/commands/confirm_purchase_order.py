"""FR-3.2: confirming a Purchase Order fixes its numbers.

**It does not change stock.** This is the one document whose confirm writes
nothing to either ledger — a PO is an intention to buy (§4.4), and goods
arrive later on a Goods Receipt. There is no ``LedgerPoster`` in this
handler for exactly that reason, and it is not an omission.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import PurchaseOrderData
from application.ports import (
    Clock,
    GoodsReceiptQueries,
    TenantUnitOfWork,
)
from application.specs import PurchaseOrderForWrite
from domain.entities import PurchaseOrder
from infrastructure.persistence.tenant.models import PurchaseOrderModel


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
        orders: TenantDbRepository[PurchaseOrder, PurchaseOrderModel],
        queries: GoodsReceiptQueries,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._orders = orders
        self._queries = queries
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: ConfirmPurchaseOrderCommand
    ) -> ResultWithData[PurchaseOrderData]:
        spec = PurchaseOrderForWrite(request.purchase_order_id)
        order = await self._orders.find_one(spec)
        if order is None:
            raise NotFoundError(
                f"purchase order {request.purchase_order_id} does not exist in this store",
                key="not_found",
                subject_key="purchase_order",
            )

        order.confirm(self._clock.now(), self._current.user_id)
        await self._orders.update(order, spec)
        await self._uow.commit()

        received = await self._queries.received_quantities(order.id)
        return ResultWithData[PurchaseOrderData].succeed_with_data(
            PurchaseOrderData.from_entity(order, received)
        )
