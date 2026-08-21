"""One Sales Invoice, and what it says depends on whether it is confirmed.

A draft's money fields are all null on purpose (FR-4.5b1): it reserves no
price, and the figures the counter reads while scanning come from the scan
responses, not from the document.

Nothing here is shaped by ``Permission.Cost.View``, because nothing on an
invoice is a cost — every figure is a price the customer is being asked
for, and a Seller must see all of them.
"""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.models import SalesInvoiceData
from application.services import DocumentLoader


class GetSalesInvoiceQuery(Query[ResultWithData[SalesInvoiceData]]):
    sales_invoice_id: UUID


class GetSalesInvoiceHandler(
    IRequestHandler[ResultWithData[SalesInvoiceData], GetSalesInvoiceQuery]
):
    def __init__(self, loader: DocumentLoader) -> None:
        self._loader = loader

    async def handle(
        self, request: GetSalesInvoiceQuery
    ) -> ResultWithData[SalesInvoiceData]:
        invoice = await self._loader.load_invoice(request.sales_invoice_id)
        return ResultWithData[SalesInvoiceData].succeed_with_data(
            SalesInvoiceData.from_entity(invoice)
        )
