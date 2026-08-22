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
"""

from uuid import UUID

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.models import SalesInvoiceData
from application.ports import (
    Clock,
    PaymentRepository,
    SalesInvoiceRepository,
    TenantUnitOfWork,
)
from application.services import DocumentLoader, LedgerPoster
from domain.enums import DocumentType


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
        invoices: SalesInvoiceRepository,
        payments: PaymentRepository,
        loader: DocumentLoader,
        poster: LedgerPoster,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._invoices = invoices
        self._payments = payments
        self._loader = loader
        self._poster = poster
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CancelSalesInvoiceCommand
    ) -> ResultWithData[SalesInvoiceData]:
        invoice = await self._loader.load_invoice(request.sales_invoice_id)

        invoice.cancel(self._clock.now(), self._current.user_id, request.reason)
        await self._poster.reverse(DocumentType.SALES_INVOICE, invoice.id)
        await self._invoices.update(invoice)
        await self._uow.commit()

        return ResultWithData[SalesInvoiceData].succeed_with_data(
            SalesInvoiceData.from_entity(
                invoice, await self._payments.list_for_invoice(invoice.id)
            )
        )
