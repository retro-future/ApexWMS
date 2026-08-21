"""FR-4.6: confirming the sale.

The invoice decides what it can decide — that it is still a draft, that it
has lines, that no handset is on it twice — and ``InvoicePoster`` does the
rest, because re-resolving a price needs the live unit and the live catalog
row (FR-4.5b1).

This handler owns the transaction, and that is what makes FR-4.5b2 true: a
line that has stopped resolving raises from the poster, the transaction
rolls back, and **nothing reaches either ledger** — not the lines that
resolved fine before it, and not the movement for the phone already marked
sold in memory.
"""

from uuid import UUID

from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.models import SalesInvoiceData
from application.ports import Clock, SalesInvoiceRepository, TenantUnitOfWork
from application.services import DocumentLoader, InvoicePoster


class ConfirmSalesInvoiceCommand(Command[ResultWithData[SalesInvoiceData]]):
    # A URL path segment, filled in by the router — never sent by the client.
    sales_invoice_id: UUID


class ConfirmSalesInvoiceHandler(
    IRequestHandler[ResultWithData[SalesInvoiceData], ConfirmSalesInvoiceCommand]
):
    def __init__(
        self,
        invoices: SalesInvoiceRepository,
        loader: DocumentLoader,
        poster: InvoicePoster,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._invoices = invoices
        self._loader = loader
        self._poster = poster
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: ConfirmSalesInvoiceCommand
    ) -> ResultWithData[SalesInvoiceData]:
        invoice = await self._loader.load_invoice(request.sales_invoice_id)

        invoice.confirm(self._clock.now(), self._current.user_id)
        await self._poster.sell(invoice)
        await self._invoices.update(invoice)
        await self._uow.commit()

        return ResultWithData[SalesInvoiceData].succeed_with_data(
            SalesInvoiceData.from_entity(invoice)
        )
