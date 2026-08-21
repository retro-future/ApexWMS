"""What has been sold, and what is still open at a counter.

Filterable by customer and by location, because both are questions a store
asks daily: what this person has bought from us, and what this till sold
today.
"""

from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import SalesInvoiceData
from application.ports import SalesInvoiceRepository
from domain.enums import DocumentStatus


class ListSalesInvoicesQuery(PagedQuery[PagedResult[SalesInvoiceData]]):
    search: str | None = None
    status: DocumentStatus | None = None
    customer_id: UUID | None = None
    location_id: UUID | None = None


class ListSalesInvoicesHandler(
    IRequestHandler[PagedResult[SalesInvoiceData], ListSalesInvoicesQuery]
):
    def __init__(self, invoices: SalesInvoiceRepository) -> None:
        self._invoices = invoices

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
        return PagedResult[SalesInvoiceData].succeed_with_data(
            data=[SalesInvoiceData.from_entity(invoice) for invoice in invoices],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
