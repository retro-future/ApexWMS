"""FR-4.8: cancelling a confirmed sale.

**Compensation, never deletion** (§4.3 rule 2). The ``−`` movements and the
``SALE_REVENUE``/``COGS`` entries the sale wrote stay exactly where they
are, and ``LedgerPoster.reverse`` appends their negation. A cancelled sale
is therefore *two* sets of rows, not zero.

The handsets are reprojected from their own timelines, which walks each one
back from ``SOLD`` to ``IN_STOCK`` at the location it was sold from. Their
asking prices are untouched throughout: an invoice-line override is a
negotiation on one sale and never reprices the unit (FR-4.5), so a phone
comes back to the shelf asking exactly what it asked before.

``SalesInvoice.cancel`` is what stops this running twice. Reversing a
reversal would re-apply the sale, and the poster deliberately holds no
guard of its own.

**A store-credit sale's debt is voided and its payments are not**
(FR-11.11). Nothing here writes to either: the debt drops out of every
balance because the balance query counts confirmed invoices only, and the
payments keep their ``PAYMENT_RECEIVED`` rows because those are booked
under ``(PAYMENT, payment.id)`` rather than under this invoice — so
``LedgerPoster.reverse`` never sees them. What comes back on the response
is the money the store is now holding and has to hand back, which is
exactly the figure refund handling needs.

**A sale with a confirmed customer return against it cannot be cancelled**
(FR-4.9g). Cancelling reverses every line at its original price, so goods
the return already restocked would arrive a second time and the customer
would be refunded twice. Cancel the returns first, or leave the sale
standing.
"""

from uuid import UUID

from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import SalesInvoiceData
from application.ports import (
    Clock,
    TenantUnitOfWork,
)
from application.services import LedgerPoster
from application.specs import (
    CustomerReturnsForInvoice,
    PaymentsForInvoice,
    SalesInvoiceForWrite,
)
from domain.entities import CustomerReturn, Payment, SalesInvoice
from domain.enums import DocumentStatus, DocumentType
from domain.errors import InvoiceHasReturnsError
from infrastructure.persistence.tenant.models import (
    CustomerReturnModel,
    PaymentModel,
    SalesInvoiceModel,
)


class CancelSalesInvoiceCommandPayload(CamelModel):
    reason: str | None = None


class CancelSalesInvoiceCommand(
    CancelSalesInvoiceCommandPayload, Command[ResultWithData[SalesInvoiceData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    sales_invoice_id: UUID


class CancelSalesInvoiceHandler(
    IRequestHandler[ResultWithData[SalesInvoiceData], CancelSalesInvoiceCommand]
):
    def __init__(
        self,
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        payments: TenantAppendOnlyRepository[Payment, PaymentModel],
        returns: TenantDbRepository[CustomerReturn, CustomerReturnModel],
        poster: LedgerPoster,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._invoices = invoices
        self._payments = payments
        self._returns = returns
        self._poster = poster
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CancelSalesInvoiceCommand
    ) -> ResultWithData[SalesInvoiceData]:
        spec = SalesInvoiceForWrite(request.sales_invoice_id)
        invoice = await self._invoices.find_one(spec)
        if invoice is None:
            raise NotFoundError(
                f"invoice {request.sales_invoice_id} does not exist in this store",
                key="not_found",
                subject_key="invoice",
            )

        await self._assert_no_standing_return(invoice)
        invoice.cancel(self._clock.now(), self._current.user_id, request.reason)
        await self._poster.reverse(DocumentType.SALES_INVOICE, invoice.id)
        await self._invoices.update(invoice, spec)
        await self._uow.commit()

        return ResultWithData[SalesInvoiceData].succeed_with_data(
            SalesInvoiceData.from_entity(
                invoice, await self._payments.find(PaymentsForInvoice(invoice.id))
            )
        )

    async def _assert_no_standing_return(self, invoice: SalesInvoice) -> None:
        """FR-4.9g. A draft return is no obstacle: it has moved nothing."""
        for document in await self._returns.find(
            CustomerReturnsForInvoice(invoice.id)
        ):
            if document.status is DocumentStatus.CONFIRMED:
                raise InvoiceHasReturnsError(
                    f"{document.number} has already taken goods back from "
                    f"{invoice.number} — cancel it first",
                    number=invoice.number,
                    return_number=document.number,
                )
