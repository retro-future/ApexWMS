"""What has been sold, and what is still open at a counter.

Filterable by customer and by location, because both are questions a store
asks daily: what this person has bought from us, and what this till sold
today.

Payments for the whole page come back in one query rather than one per
row. A list that showed ``remaining = 0`` on a store-credit sale because
it never looked would be worse than one that showed nothing at all.
"""

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from application.common.specification import Specification
from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import SalesInvoiceData
from application.specs import SalesInvoiceBrowse
from domain.entities import Payment, SalesInvoice
from domain.enums import DocumentStatus, PaymentType
from infrastructure.persistence.tenant.models import PaymentModel, SalesInvoiceModel


class ListSalesInvoicesQuery(PagedQuery[PagedResult[SalesInvoiceData]]):
    search: str | None = None
    status: DocumentStatus | None = None
    customer_id: UUID | None = None
    location_id: UUID | None = None
    payment_type: PaymentType | None = None
    # The month-end drill-down scopes by when a sale was *confirmed*, not opened.
    confirmed_from: datetime | None = None
    confirmed_to: datetime | None = None


class ListSalesInvoicesHandler(
    IRequestHandler[PagedResult[SalesInvoiceData], ListSalesInvoicesQuery]
):
    def __init__(
        self,
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        payments: TenantAppendOnlyRepository[Payment, PaymentModel],
    ) -> None:
        self._invoices = invoices
        self._payments = payments

    async def handle(
        self, request: ListSalesInvoicesQuery
    ) -> PagedResult[SalesInvoiceData]:
        spec = SalesInvoiceBrowse(
            search=request.search,
            status=request.status,
            customer_id=request.customer_id,
            location_id=request.location_id,
            payment_type=request.payment_type,
            confirmed_from=request.confirmed_from,
            confirmed_to=request.confirmed_to,
        )
        total = await self._invoices.count(spec)
        invoices = await self._invoices.find(
            spec.page(request.page, request.page_size)
        )
        ids = [invoice.id for invoice in invoices]
        paid: defaultdict[UUID, list[Payment]] = defaultdict(list)
        if ids:
            spec = (
                Specification(PaymentModel)
                .where(PaymentModel.sales_invoice_id.in_(ids))
                .order(PaymentModel.occurred_at, PaymentModel.id)
            )
            for payment in await self._payments.find(spec):
                paid[payment.sales_invoice_id].append(payment)
        return PagedResult[SalesInvoiceData].succeed_with_data(
            data=[
                SalesInvoiceData.from_entity(invoice, paid.get(invoice.id, []))
                for invoice in invoices
            ],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
