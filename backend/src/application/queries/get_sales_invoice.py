"""One Sales Invoice, and what it says depends on whether it is confirmed.

A draft's money fields are all null on purpose (FR-4.5b1): it reserves no
price, and the figures the counter reads while scanning come from the scan
responses, not from the document.

Nothing here is shaped by ``Permission.Cost.View``, because nothing on an
invoice is a cost — every figure is a price the customer is being asked
for, and a Seller must see all of them.
"""

from uuid import UUID

from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import ExchangeRateData, SalesInvoiceData
from application.ports import Clock
from application.services import PeriodResolver
from application.specs import (
    CustomerReturnsForInvoice,
    PaymentsForInvoice,
    SalesInvoiceById,
)
from domain.entities import CustomerReturn, ExchangeRate, Payment, SalesInvoice
from infrastructure.persistence.tenant.models import (
    CustomerReturnModel,
    ExchangeRateModel,
    PaymentModel,
    SalesInvoiceModel,
)


class GetSalesInvoiceQuery(Query[ResultWithData[SalesInvoiceData]]):
    sales_invoice_id: UUID


class GetSalesInvoiceHandler(
    IRequestHandler[ResultWithData[SalesInvoiceData], GetSalesInvoiceQuery]
):
    def __init__(
        self,
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        payments: TenantAppendOnlyRepository[Payment, PaymentModel],
        returns: TenantDbRepository[CustomerReturn, CustomerReturnModel],
        rates: TenantAppendOnlyRepository[ExchangeRate, ExchangeRateModel],
        periods: PeriodResolver,
        clock: Clock,
    ) -> None:
        self._invoices = invoices
        self._payments = payments
        self._returns = returns
        self._rates = rates
        self._periods = periods
        self._clock = clock

    async def handle(
        self, request: GetSalesInvoiceQuery
    ) -> ResultWithData[SalesInvoiceData]:
        invoice = await self._invoices.find_one(
            SalesInvoiceById(request.sales_invoice_id)
        )
        if invoice is None:
            raise NotFoundError(
                f"invoice {request.sales_invoice_id} does not exist in this store",
                key="not_found",
                subject_key="invoice",
            )
        return ResultWithData[SalesInvoiceData].succeed_with_data(
            SalesInvoiceData.from_entity(
                invoice,
                await self._payments.find(PaymentsForInvoice(invoice.id)),
                await self._returns.find(CustomerReturnsForInvoice(invoice.id)),
                sale_rate=await self._quoted_rate(invoice),
            )
        )

    async def _quoted_rate(self, invoice: SalesInvoice) -> ExchangeRateData | None:
        if invoice.sale_rate_id is None:
            return None
        rate = await self._rates.get(invoice.sale_rate_id)
        if rate is None:
            return None
        return ExchangeRateData.from_entity(
            rate, await self._periods.today(self._clock.now())
        )
