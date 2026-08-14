"""FR-3.1: an Owner or Manager prices a line the order was raised without.

A PO may be created as just products and quantities, price unknown. This is
where that gap closes, one line at a time, while the order is still a
draft — the same shape ``price_receipt_unit.py`` uses for a scanned
handset. ``PurchaseOrder.confirm()`` is what refuses to let a line through
still unpriced.
"""

from uuid import UUID

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import PurchaseOrderData
from application.ports import PurchaseOrderRepository, TenantUnitOfWork
from application.services import DocumentLoader
from domain.entities import PurchaseOrder, PurchaseOrderLine
from domain.value_objects import Money


class PricePurchaseOrderLineCommandPayload(CamelModel):
    unit_cost: str | int


class PricePurchaseOrderLineCommand(
    PricePurchaseOrderLineCommandPayload, Command[ResultWithData[PurchaseOrderData]]
):
    # URL path segments, filled in by the router — never sent by the client.
    purchase_order_id: UUID
    line_id: UUID


class PricePurchaseOrderLineHandler(
    IRequestHandler[ResultWithData[PurchaseOrderData], PricePurchaseOrderLineCommand]
):
    def __init__(
        self,
        orders: PurchaseOrderRepository,
        loader: DocumentLoader,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._orders = orders
        self._loader = loader
        self._uow = uow
        self._current = current

    async def handle(
        self, request: PricePurchaseOrderLineCommand
    ) -> ResultWithData[PurchaseOrderData]:
        order = await self._loader.load_order(request.purchase_order_id)
        order.assert_editable()

        line = self._find(order, request.line_id)
        line.unit_cost = Money.from_major(request.unit_cost, line.currency)
        # Re-run the invariants over the edited row: a negative amount must
        # fail here, not at the column.
        line.__post_init__()

        await self._orders.update_line(line)
        await self._uow.commit()

        return ResultWithData[PurchaseOrderData].succeed_with_data(
            PurchaseOrderData.from_entity(order, {})
        )

    @staticmethod
    def _find(order: PurchaseOrder, line_id: UUID) -> PurchaseOrderLine:
        for line in order.lines:
            if line.id == line_id:
                return line
        raise NotFoundError(f"{order.number} has no line {line_id}")
