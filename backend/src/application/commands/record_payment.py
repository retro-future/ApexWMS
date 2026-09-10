"""FR-11.6: the customer hands money over.

Against a store-credit sale that is a payment on the debt; on a sale
settled at confirm it is a tender, which is what the till has to balance
against. ``PaymentPoster`` decides which from the invoice, so this handler
does not branch.

Writes a ``PAYMENT_RECEIVED`` or ``TENDER_RECEIVED`` transaction and
**never** a ``SALE_REVENUE`` one (FR-11.7): the revenue was booked in full
the moment the sale confirmed, and re-booking it per instalment is the
signature bug of naive credit systems. ``PaymentPoster`` is what makes that structural: it is the
only thing that writes a payment, and it can only emit one category.

The whole invoice comes back rather than the payment alone, so the counter
sees the recomputed remaining balance without a second round trip.
"""

from uuid import UUID

from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.errors import NotFoundError
from application.models import SalesInvoiceData
from application.ports import TenantUnitOfWork
from application.services import PaymentPoster, SalePriceParser
from application.specs import PaymentsForInvoice, SalesInvoiceById
from domain.entities import Payment, SalesInvoice
from domain.enums import PaymentMethod
from domain.errors import InvalidMoneyError
from domain.value_objects import Currency
from infrastructure.persistence.tenant.models import PaymentModel, SalesInvoiceModel


class RecordPaymentCommandPayload(CamelModel):
    # A major-unit string or int — never a JSON float (§4.5).
    amount: str | int
    # Som unless the counter says otherwise, which is what a debt is always
    # written in; a tender may be either.
    currency: Currency = Currency.UZS
    method: PaymentMethod = PaymentMethod.CASH
    note: str | None = None


class RecordPaymentCommand(
    RecordPaymentCommandPayload, Command[ResultWithData[SalesInvoiceData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    sales_invoice_id: UUID


class RecordPaymentHandler(
    IRequestHandler[ResultWithData[SalesInvoiceData], RecordPaymentCommand]
):
    def __init__(
        self,
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        poster: PaymentPoster,
        payments: TenantAppendOnlyRepository[Payment, PaymentModel],
        prices: SalePriceParser,
        uow: TenantUnitOfWork,
    ) -> None:
        self._invoices = invoices
        self._poster = poster
        self._payments = payments
        self._prices = prices
        self._uow = uow

    async def handle(
        self, request: RecordPaymentCommand
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
        amount = self._prices.parse(request.amount, request.currency)
        if amount is None:
            raise InvalidMoneyError("a payment states an amount")

        await self._poster.receive(invoice, amount, request.method, request.note)
        await self._uow.commit()

        return ResultWithData[SalesInvoiceData].succeed_with_data(
            SalesInvoiceData.from_entity(
                invoice, await self._payments.find(PaymentsForInvoice(invoice.id))
            )
        )
