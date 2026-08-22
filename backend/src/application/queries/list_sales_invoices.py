"""What has been sold, and what is still open at a counter.

Filterable by customer and by location, because both are questions a store
asks daily: what this person has bought from us, and what this till sold
today.

Payments for the whole page come back in one query rather than one per
row. A list that showed ``remaining = 0`` on a store-credit sale because
it never looked would be worse than one that showed nothing at all.
"""

from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import SalesInvoiceData
from application.ports import PaymentRepository, SalesInvoiceRepository
from domain.enums import DocumentStatus


class ListSalesInvoicesQuery(PagedQuery[PagedResult[SalesInvoiceData]]):
    search: str | None = None
    status: DocumentStatus | None = None
    customer_id: UUID | None = None
    location_id: UUID | None = None


class ListSalesInvoicesHandler(
    IRequestHandler[PagedResult[SalesInvoiceData], ListSalesInvoicesQuery]
):
    def __init__(
        self, invoices: SalesInvoiceRepository, payments: PaymentRepository
    ) -> None:
        self._invoices = invoices
        self._payments = payments

    async def handle(
        self, request: ListSalesInvoicesQuery
    ) -> PagedResult[SalesInvoiceData]:
        invoices, total = await self._invoices.list_page(
            page=request.page,
            page_size=request.page_size,
            search=request.search,
            status=request.status,
            customer_id=request.customer_id,
            location_id=request.location_id,
        )
        paid = await self._payments.list_for_invoices([i.id for i in invoices])
        return PagedResult[SalesInvoiceData].succeed_with_data(
            data=[
                SalesInvoiceData.from_entity(invoice, paid.get(invoice.id, []))
                for invoice in invoices
            ],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
