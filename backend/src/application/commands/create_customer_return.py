"""FR-4.9: a Manager opens a return against a sale that already happened.

Header only — no lines. Every line arrives by scan, because that is what
happens at the counter: the customer puts the phone down and somebody pulls
the trigger on it.

**The invoice is named at creation and cannot change.** Everything the
return needs comes from it: which goods may come back, what each was
charged, what it cost, and whether there is a debt to relieve. Opening the
document against the sale rather than picking a sale at confirm is what lets
the scan refuse a handset this customer never bought.

The location is the return's own, not the invoice's. Goods sold from a shop
that has since closed still have to land somewhere, and stock lives at a
place (§4.3).
"""

from uuid import UUID, uuid4

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import CustomerReturnData
from application.ports import Clock, TenantUnitOfWork
from application.services import DocumentNumberer
from application.specs import SalesInvoiceById
from domain.entities import CustomerReturn, Location, SalesInvoice
from domain.enums import CustomerReturnReason, DocumentStatus, DocumentType
from domain.errors import DocumentNotConfirmedError
from infrastructure.persistence.tenant.models import (
    CustomerReturnModel,
    LocationModel,
    SalesInvoiceModel,
)


class CreateCustomerReturnCommand(Command[ResultWithData[CustomerReturnData]]):
    sales_invoice_id: UUID
    location_id: UUID
    reason: CustomerReturnReason
    note: str | None = None


class CreateCustomerReturnHandler(
    IRequestHandler[ResultWithData[CustomerReturnData], CreateCustomerReturnCommand]
):
    def __init__(
        self,
        returns: TenantDbRepository[CustomerReturn, CustomerReturnModel],
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        locations: TenantDbRepository[Location, LocationModel],
        numberer: DocumentNumberer,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._returns = returns
        self._invoices = invoices
        self._locations = locations
        self._numberer = numberer
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CreateCustomerReturnCommand
    ) -> ResultWithData[CustomerReturnData]:
        invoice = await self._confirmed_invoice(request.sales_invoice_id)
        if await self._locations.get(request.location_id) is None:
            raise NotFoundError(
                f"location {request.location_id} does not exist in this store",
                key="not_found",
                subject_key="location",
            )

        document = CustomerReturn(
            id=uuid4(),
            number=await self._numberer.next(DocumentType.CUSTOMER_RETURN),
            status=DocumentStatus.DRAFT,
            sales_invoice_id=invoice.id,
            # Copied, not looked up later: the return is about this sale,
            # and a customer record edited afterwards must not re-point it.
            customer_id=invoice.customer_id,
            location_id=request.location_id,
            reason=request.reason,
            note=request.note,
            created_by=self._current.user_id,
            created_at=self._clock.now(),
        )
        await self._returns.add(document)
        await self._uow.commit()

        return ResultWithData[CustomerReturnData].succeed_with_data(
            CustomerReturnData.from_entity(document)
        )

    async def _confirmed_invoice(self, sales_invoice_id: UUID) -> SalesInvoice:
        invoice = await self._invoices.find_one(SalesInvoiceById(sales_invoice_id))
        if invoice is None:
            raise NotFoundError(
                f"sales invoice {sales_invoice_id} does not exist in this store",
                key="not_found",
                subject_key="sales_invoice",
            )
        # A draft sold nothing and a cancelled sale already gave everything
        # back; either would put goods into stock the ledger never removed.
        if invoice.status is not DocumentStatus.CONFIRMED:
            raise DocumentNotConfirmedError(
                f"{invoice.number} is {invoice.status.value}, so there is no sale to "
                "return against",
                key="return_needs_confirmed_sale",
                number=invoice.number,
            )
        return invoice
