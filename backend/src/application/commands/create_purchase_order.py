"""FR-3.1: a Manager raises a Purchase Order.

It is a `DRAFT` and it moves nothing. Each line takes its currency from
its product (FR-2.7), so an order for a phone and a case carries two
currencies and no combined total.
"""

from uuid import UUID, uuid4

from pydantic import Field

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser, LineInput
from application.errors import NotFoundError
from application.models import PurchaseOrderData
from application.ports import (
    Clock,
    TenantUnitOfWork,
)
from application.services import DocumentLineBuilder, DocumentNumberer
from domain.entities import PurchaseOrder, Supplier
from domain.enums import DocumentStatus, DocumentType
from infrastructure.persistence.tenant.models import PurchaseOrderModel, SupplierModel


class OrderLine(CamelModel):
    product_id: UUID
    quantity: int = Field(gt=0)
    # A string or a whole number, never a JSON float (§4.5 rule 2). Absent
    # when the price is not yet agreed with the supplier; set later, per
    # line, via PricePurchaseOrderLineCommand.
    unit_cost: str | int | None = None


class CreatePurchaseOrderCommand(Command[ResultWithData[PurchaseOrderData]]):
    supplier_id: UUID
    lines: list[OrderLine] = Field(min_length=1)
    note: str | None = None


class CreatePurchaseOrderHandler(
    IRequestHandler[ResultWithData[PurchaseOrderData], CreatePurchaseOrderCommand]
):
    def __init__(
        self,
        orders: TenantDbRepository[PurchaseOrder, PurchaseOrderModel],
        suppliers: TenantDbRepository[Supplier, SupplierModel],
        builder: DocumentLineBuilder,
        numberer: DocumentNumberer,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._orders = orders
        self._suppliers = suppliers
        self._builder = builder
        self._numberer = numberer
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CreatePurchaseOrderCommand
    ) -> ResultWithData[PurchaseOrderData]:
        if await self._suppliers.get(request.supplier_id) is None:
            raise NotFoundError(
                f"supplier {request.supplier_id} does not exist in this store"
            )

        order_id = uuid4()
        order = PurchaseOrder(
            id=order_id,
            number=await self._numberer.next(DocumentType.PURCHASE_ORDER),
            status=DocumentStatus.DRAFT,
            note=request.note,
            created_by=self._current.user_id,
            created_at=self._clock.now(),
            supplier_id=request.supplier_id,
            lines=await self._builder.order_lines(
                order_id,
                [
                    LineInput(line.product_id, line.quantity, line.unit_cost)
                    for line in request.lines
                ],
            ),
        )
        await self._orders.add(order)
        await self._uow.commit()
        return ResultWithData[PurchaseOrderData].succeed_with_data(
            PurchaseOrderData.from_entity(order, {})
        )
