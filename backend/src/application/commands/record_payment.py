"""FR-11.6: the customer pays some of what they owe.

Writes a ``PAYMENT_RECEIVED`` transaction and **never** a ``SALE_REVENUE``
one (FR-11.7) — the revenue for this sale was booked in full the moment it
confirmed, and re-booking it per instalment is the signature bug of naive
credit systems. ``PaymentPoster`` is what makes that structural: it is the
only thing that writes a payment, and it can only emit one category.

The whole invoice comes back rather than the payment alone, so the counter
sees the recomputed remaining balance without a second round trip.
"""

from uuid import UUID

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.models import SalesInvoiceData
from application.ports import PaymentRepository, TenantUnitOfWork
from application.services import DocumentLoader, PaymentPoster, SalePriceParser
from domain.enums import PaymentMethod
from domain.errors import InvalidMoneyError
from domain.value_objects import Currency


class RecordPaymentCommandPayload(CamelModel):
    # Som, as a major-unit string or int — never a JSON float (§4.5).
    amount: str | int
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
        loader: DocumentLoader,
        poster: PaymentPoster,
        payments: PaymentRepository,
        prices: SalePriceParser,
        uow: TenantUnitOfWork,
    ) -> None:
        self._loader = loader
        self._poster = poster
        self._payments = payments
        self._prices = prices
        self._uow = uow

    async def handle(
        self, request: RecordPaymentCommand
    ) -> ResultWithData[SalesInvoiceData]:
        invoice = await self._loader.load_invoice(request.sales_invoice_id)
        amount = self._prices.parse(request.amount, Currency.UZS)
        if amount is None:
            raise InvalidMoneyError("a payment states an amount")

        await self._poster.receive(invoice, amount, request.method, request.note)
        await self._uow.commit()

        return ResultWithData[SalesInvoiceData].succeed_with_data(
            SalesInvoiceData.from_entity(
                invoice, await self._payments.list_for_invoice(invoice.id)
            )
        )
