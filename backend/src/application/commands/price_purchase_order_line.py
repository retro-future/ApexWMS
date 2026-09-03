"""FR-3.1: an Owner or Manager prices a line the order was raised without.

A PO may be created as just products and quantities, price unknown. This is
where that gap closes, one line at a time, while the order is still a
draft — the same shape ``price_receipt_unit.py`` uses for a scanned
handset. Pricing here is optional: an order confirms with or without it,
and an unpriced line is priced later on the Goods Receipt.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import PurchaseOrderData
from application.ports import TenantUnitOfWork
from application.specs import PurchaseOrderForWrite
from domain.entities import PurchaseOrder, PurchaseOrderLine
from domain.value_objects import Money
from infrastructure.persistence.tenant.models import PurchaseOrderModel


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
        orders: TenantDbRepository[PurchaseOrder, PurchaseOrderModel],
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._orders = orders
        self._uow = uow
        self._current = current

    async def handle(
        self, request: PricePurchaseOrderLineCommand
    ) -> ResultWithData[PurchaseOrderData]:
        spec = PurchaseOrderForWrite(request.purchase_order_id)
        order = await self._orders.find_one(spec)
        if order is None:
            raise NotFoundError(
                f"purchase order {request.purchase_order_id} does not exist in this store",
                key="not_found",
                subject_key="purchase_order",
            )
        order.assert_editable()

        line = self._find(order, request.line_id)
        line.unit_cost = Money.from_major(request.unit_cost, line.currency)
        # Re-run the invariants over the edited row: a negative amount must
        # fail here, not at the column.
        line.__post_init__()

        await self._orders.update(order, spec)
        await self._uow.commit()

        return ResultWithData[PurchaseOrderData].succeed_with_data(
            PurchaseOrderData.from_entity(order, {})
        )

    @staticmethod
    def _find(order: PurchaseOrder, line_id: UUID) -> PurchaseOrderLine:
        for line in order.lines:
            if line.id == line_id:
                return line
        raise NotFoundError(f"{order.number} has no line {line_id}", key="not_found_line")
