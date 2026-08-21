"""FR-4.5c: take a line off a draft invoice.

A draft has written nothing — no movement, no money entry, no debt — so
there is nothing to keep consistent and a line comes off with no trace
kept. The moment that stops being true is confirm, which is why
``assert_editable`` is the whole of the rule here (§4.4, FR-4.5d).
"""

from uuid import UUID

from application.core import Command, IRequestHandler, ResultWithData
from application.errors import NotFoundError
from application.models import SalesInvoiceData
from application.ports import SalesInvoiceRepository, TenantUnitOfWork
from application.services import DocumentLoader


class UnscanInvoiceLineCommand(Command[ResultWithData[SalesInvoiceData]]):
    # URL path segments, filled in by the router — never sent by the client.
    sales_invoice_id: UUID
    line_id: UUID


class UnscanInvoiceLineHandler(
    IRequestHandler[ResultWithData[SalesInvoiceData], UnscanInvoiceLineCommand]
):
    def __init__(
        self,
        invoices: SalesInvoiceRepository,
        loader: DocumentLoader,
        uow: TenantUnitOfWork,
    ) -> None:
        self._invoices = invoices
        self._loader = loader
        self._uow = uow

    async def handle(
        self, request: UnscanInvoiceLineCommand
    ) -> ResultWithData[SalesInvoiceData]:
        invoice = await self._loader.load_invoice(request.sales_invoice_id)
        invoice.assert_editable()

        line = next((one for one in invoice.lines if one.id == request.line_id), None)
        if line is None:
            raise NotFoundError(f"{invoice.number} has no line {request.line_id}")

        invoice.lines.remove(line)
        await self._invoices.remove_line(line.id)
        await self._uow.commit()

        return ResultWithData[SalesInvoiceData].succeed_with_data(
            SalesInvoiceData.from_entity(invoice)
        )
