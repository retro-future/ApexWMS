"""FR-4.1: a Seller opens an invoice.

Header only — no lines. Every line arrives by scan (FR-4.2), because that
is what happens at a counter: the customer puts a phone down and the
operator pulls the trigger. There is no screen where somebody types a
product id and a quantity into a new sale.

The invoice has no currency of its own. Each line takes its currency from
its product (FR-2.7), so one sale may hold a USD phone and a UZS case and
present two subtotals with no field anywhere for their sum.

``payment_type`` here is the Seller's intention (FR-11.1), so the till can
show the right controls while scanning. The terms that are actually struck
arrive in the confirm body, because the som debt and the down payment are
only known once the customer has agreed to them.
"""

from uuid import UUID, uuid4

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import SalesInvoiceData
from application.ports import (
    Clock,
    TenantUnitOfWork,
)
from application.services import DocumentNumberer
from domain.entities import Customer, Location, SalesInvoice
from domain.enums import DocumentStatus, DocumentType, PaymentType
from infrastructure.persistence.tenant.models import (
    CustomerModel,
    LocationModel,
    SalesInvoiceModel,
)


class CreateSalesInvoiceCommand(Command[ResultWithData[SalesInvoiceData]]):
    location_id: UUID
    # Optional: a walk-in buying a case for cash is not a record the store
    # needs to keep (FR-4.1).
    customer_id: UUID | None = None
    note: str | None = None
    payment_type: PaymentType = PaymentType.PAID_IN_FULL


class CreateSalesInvoiceHandler(
    IRequestHandler[ResultWithData[SalesInvoiceData], CreateSalesInvoiceCommand]
):
    def __init__(
        self,
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        locations: TenantDbRepository[Location, LocationModel],
        customers: TenantDbRepository[Customer, CustomerModel],
        numberer: DocumentNumberer,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._invoices = invoices
        self._locations = locations
        self._customers = customers
        self._numberer = numberer
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CreateSalesInvoiceCommand
    ) -> ResultWithData[SalesInvoiceData]:
        await self._assert_parties_exist(request)

        invoice = SalesInvoice(
            id=uuid4(),
            number=await self._numberer.next(DocumentType.SALES_INVOICE),
            status=DocumentStatus.DRAFT,
            location_id=request.location_id,
            customer_id=request.customer_id,
            note=request.note,
            payment_type=request.payment_type,
            created_by=self._current.user_id,
            created_at=self._clock.now(),
        )
        await self._invoices.add(invoice)
        await self._uow.commit()

        return ResultWithData[SalesInvoiceData].succeed_with_data(
            SalesInvoiceData.from_entity(invoice)
        )

    async def _assert_parties_exist(self, request: CreateSalesInvoiceCommand) -> None:
        if await self._locations.get(request.location_id) is None:
            raise NotFoundError(f"location {request.location_id} does not exist in this store")
        if request.customer_id is None:
            return
        if await self._customers.get(request.customer_id) is None:
            raise NotFoundError(f"customer {request.customer_id} does not exist in this store")
