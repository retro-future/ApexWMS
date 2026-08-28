"""FR-3.3, FR-3.3b: a Storekeeper opens a Goods Receipt.

The receipt states where the goods came from. ``SUPPLIER`` names a
supplier; ``TRADE_IN`` names none and may name the walk-in customer the
handset was bought from. A receipt raised against a Purchase Order is
always ``SUPPLIER`` and pre-fills its lines from the order — and the order
must already be ``CONFIRMED``, which is what guarantees every line it
hands over already has a price (FR-3.1, FR-3.2).

The source says nothing about the goods. Whether each handset is new,
refurbished or used is stated per scan, and a supplier delivery of used
stock is an ordinary thing rather than a contradiction.
"""

from uuid import UUID, uuid4

from pydantic import Field

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser, LineInput
from application.errors import NotFoundError
from application.models import GoodsReceiptData
from application.ports import (
    Clock,
    CustomerRepository,
    GoodsReceiptRepository,
    LocationRepository,
    TenantUnitOfWork,
)
from application.services import DocumentLineBuilder, DocumentNumberer
from application.specs import PurchaseOrderById, SupplierById
from domain.entities import GoodsReceipt, PurchaseOrder, Supplier
from domain.enums import AcquisitionSource, DocumentStatus, DocumentType
from domain.errors import DocumentNotConfirmedError, OverReceiptError
from domain.permissions import Permission
from infrastructure.persistence.tenant.models import PurchaseOrderModel, SupplierModel


class ReceiptLine(CamelModel):
    product_id: UUID
    quantity: int = Field(gt=0)
    # Quantity lines only, and optional even then: a Storekeeper opens the
    # receipt and an Owner or Manager states the cost (FR-3.4b). A cost sent
    # for a serialized line is dropped — each handset carries its own.
    unit_cost: str | int | None = None


class CreateGoodsReceiptCommand(Command[ResultWithData[GoodsReceiptData]]):
    location_id: UUID
    acquisition_source: AcquisitionSource = AcquisitionSource.SUPPLIER
    supplier_id: UUID | None = None
    customer_id: UUID | None = None
    purchase_order_id: UUID | None = None
    # Absent when the receipt is raised from a Purchase Order, which
    # pre-fills them (FR-3.3).
    lines: list[ReceiptLine] | None = None
    note: str | None = None


class CreateGoodsReceiptHandler(
    IRequestHandler[ResultWithData[GoodsReceiptData], CreateGoodsReceiptCommand]
):
    def __init__(
        self,
        receipts: GoodsReceiptRepository,
        orders: TenantDbRepository[PurchaseOrder, PurchaseOrderModel],
        suppliers: TenantDbRepository[Supplier, SupplierModel],
        customers: CustomerRepository,
        locations: LocationRepository,
        builder: DocumentLineBuilder,
        numberer: DocumentNumberer,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._receipts = receipts
        self._orders = orders
        self._suppliers = suppliers
        self._customers = customers
        self._locations = locations
        self._builder = builder
        self._numberer = numberer
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CreateGoodsReceiptCommand
    ) -> ResultWithData[GoodsReceiptData]:
        await self._assert_parties_exist(request)
        order = await self._linked_order(request)
        received = await self._receipts.received_quantities(order.id) if order else {}

        line_inputs = self._line_inputs(request, order, received)
        if order is not None:
            self._assert_within_order(order, received, line_inputs)

        receipt_id = uuid4()
        receipt = GoodsReceipt(
            id=receipt_id,
            number=await self._numberer.next(DocumentType.GOODS_RECEIPT),
            status=DocumentStatus.DRAFT,
            note=request.note,
            created_by=self._current.user_id,
            created_at=self._clock.now(),
            # A receipt against an order is always from that order's
            # supplier: the goods were ordered from them.
            acquisition_source=(
                AcquisitionSource.SUPPLIER if order else request.acquisition_source
            ),
            supplier_id=order.supplier_id if order else request.supplier_id,
            customer_id=request.customer_id,
            purchase_order_id=request.purchase_order_id,
            location_id=request.location_id,
            lines=await self._builder.receipt_lines(receipt_id, line_inputs),
        )
        await self._receipts.add(receipt)
        await self._uow.commit()
        return ResultWithData[GoodsReceiptData].succeed_with_data(
            GoodsReceiptData.from_entity(
                receipt, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )

    async def _assert_parties_exist(self, request: CreateGoodsReceiptCommand) -> None:
        if await self._locations.get(request.location_id) is None:
            raise NotFoundError(
                f"location {request.location_id} does not exist in this store"
            )
        if request.supplier_id is not None and not await self._suppliers.exists(
            SupplierById(request.supplier_id)
        ):
            raise NotFoundError(
                f"supplier {request.supplier_id} does not exist in this store"
            )
        if (
            request.customer_id is not None
            and await self._customers.get(request.customer_id) is None
        ):
            raise NotFoundError(
                f"customer {request.customer_id} does not exist in this store"
            )

    async def _linked_order(
        self, request: CreateGoodsReceiptCommand
    ) -> PurchaseOrder | None:
        if request.purchase_order_id is None:
            return None
        order = await self._orders.find_one(
            PurchaseOrderById(request.purchase_order_id)
        )
        if order is None:
            raise NotFoundError(
                f"purchase order {request.purchase_order_id} does not exist in this store"
            )
        if order.status is not DocumentStatus.CONFIRMED:
            raise DocumentNotConfirmedError(
                f"{order.number} is {order.status.value}; a receipt can only be "
                "raised against a confirmed order"
            )
        return order

    @staticmethod
    def _line_inputs(
        request: CreateGoodsReceiptCommand,
        order: PurchaseOrder | None,
        received: dict[UUID, int],
    ) -> list[LineInput]:
        """The order's remaining lines when one is named, otherwise the request's.

        A receipt raised from an order starts as "everything still
        outstanding", not the order's original total, which a prior
        receipt may have already partly covered. The storekeeper then scans
        what actually turned up, and FR-3.9's received-versus-ordered
        figure reports the difference.
        """
        if order is not None and not request.lines:
            lines: list[LineInput] = []
            for line in order.lines:
                # `_linked_order` has already refused anything but a
                # CONFIRMED order, and `PurchaseOrder.confirm()` refuses to
                # confirm while any line is unpriced.
                assert line.unit_cost is not None
                outstanding = line.quantity - received.get(line.product_id, 0)
                if outstanding > 0:
                    lines.append(
                        LineInput(line.product_id, outstanding, line.unit_cost.as_major())
                    )
            return lines
        return [
            LineInput(line.product_id, line.quantity, line.unit_cost)
            for line in (request.lines or [])
        ]

    @staticmethod
    def _assert_within_order(
        order: PurchaseOrder, received: dict[UUID, int], lines: list[LineInput]
    ) -> None:
        """FR-3.9: a receipt may never take an order past what it ordered."""
        ordered = order.ordered_quantities()
        if not lines:
            raise OverReceiptError(f"{order.number} has nothing left to receive")
        requested: dict[UUID, int] = {}
        for line in lines:
            requested[line.product_id] = requested.get(line.product_id, 0) + line.quantity
        for product_id, quantity in requested.items():
            total = received.get(product_id, 0) + quantity
            if total > ordered.get(product_id, 0):
                raise OverReceiptError(
                    f"{order.number} ordered {ordered.get(product_id, 0)} of "
                    f"{product_id}, already received {received.get(product_id, 0)}, "
                    f"this receipt would take it to {total}"
                )
