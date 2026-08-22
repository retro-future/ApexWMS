"""FR-11.8: undoing a payment that should not have been recorded.

**Compensation, never deletion**, the same rule both ledgers keep. The
original row stays and a negative one is written beside it, so a reversed
payment is two rows rather than none — the mistake is part of the history,
and the customer's balance goes back up by exactly what came off it.

Allowed on a cancelled invoice too: cancelling voids the debt but leaves
the payments standing for refund handling (FR-11.11), and reversing one is
how the refund gets recorded.
"""

from uuid import UUID

from application.core import Command, IRequestHandler, ResultWithData
from application.errors import NotFoundError
from application.models import SalesInvoiceData
from application.ports import PaymentRepository, TenantUnitOfWork
from application.services import DocumentLoader, PaymentPoster


class ReversePaymentCommand(Command[ResultWithData[SalesInvoiceData]]):
    # A URL path segment, filled in by the router — never sent by the client.
    payment_id: UUID


class ReversePaymentHandler(
    IRequestHandler[ResultWithData[SalesInvoiceData], ReversePaymentCommand]
):
    def __init__(
        self,
        payments: PaymentRepository,
        loader: DocumentLoader,
        poster: PaymentPoster,
        uow: TenantUnitOfWork,
    ) -> None:
        self._payments = payments
        self._loader = loader
        self._poster = poster
        self._uow = uow

    async def handle(
        self, request: ReversePaymentCommand
    ) -> ResultWithData[SalesInvoiceData]:
        original = await self._payments.get(request.payment_id)
        if original is None:
            raise NotFoundError(f"payment {request.payment_id} does not exist in this store")

        invoice = await self._loader.load_invoice(original.sales_invoice_id)
        await self._poster.reverse(original, invoice)
        await self._uow.commit()

        return ResultWithData[SalesInvoiceData].succeed_with_data(
            SalesInvoiceData.from_entity(
                invoice, await self._payments.list_for_invoice(invoice.id)
            )
        )
