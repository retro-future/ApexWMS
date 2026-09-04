"""FR-4.9f: confirming a return, and the only writer of ``SALES_RETURN_REFUND``.

The same shape as ``ConfirmSupplierReturnHandler``: the handler decides
nothing about goods coming back. It asks the aggregate whether the return
may be confirmed, asks ``CustomerReturnPoster`` to put the goods on the
shelf and the money back in the customer's hand, and owns the transaction
both ledgers are written inside (FR-10.1).

Two things it does decide, because neither is a fact about the return's own
lines.

**The debt relief arrives here, not at creation** (FR-4.9d), for the reason
the invoice takes its payment terms at confirm: what is still outstanding
changes while a draft sits open, so a figure entered earlier could be capped
against a balance that has since moved.

**The double-return guard runs here too.** A second draft can be opened
against the same sale, and only the first to confirm may take the goods.
Discovering it at the scan is a courtesy; discovering it here is what makes
it true.
"""

from collections.abc import Sequence
from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import CustomerReturnData
from application.ports import Clock, TenantUnitOfWork
from application.services import CustomerReturnPoster, SalePriceParser, remaining_on
from application.specs import (
    CustomerReturnForWrite,
    CustomerReturnsForInvoice,
    PaymentsForInvoice,
    SalesInvoiceById,
)
from domain.entities import CustomerReturn, Payment, SalesInvoice
from domain.enums import DocumentStatus
from domain.errors import (
    AlreadyReturnedError,
    DebtReliefError,
    DocumentNotConfirmedError,
)
from domain.value_objects import Currency
from infrastructure.persistence.tenant.models import (
    CustomerReturnModel,
    PaymentModel,
    SalesInvoiceModel,
)


class ConfirmCustomerReturnCommandPayload(CamelModel):
    # Som, and never a conversion of the line refunds (§4.7). Absent on a
    # sale that opened no debt, which is most of them.
    debt_relief: str | int | None = None


class ConfirmCustomerReturnCommand(
    ConfirmCustomerReturnCommandPayload, Command[ResultWithData[CustomerReturnData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    customer_return_id: UUID


class ConfirmCustomerReturnHandler(
    IRequestHandler[ResultWithData[CustomerReturnData], ConfirmCustomerReturnCommand]
):
    def __init__(
        self,
        returns: TenantDbRepository[CustomerReturn, CustomerReturnModel],
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        payments: TenantDbRepository[Payment, PaymentModel],
        poster: CustomerReturnPoster,
        prices: SalePriceParser,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._returns = returns
        self._invoices = invoices
        self._payments = payments
        self._poster = poster
        self._prices = prices
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: ConfirmCustomerReturnCommand
    ) -> ResultWithData[CustomerReturnData]:
        spec = CustomerReturnForWrite(request.customer_return_id)
        document = await self._returns.find_one(spec)
        if document is None:
            raise NotFoundError(
                f"customer return {request.customer_return_id} does not exist in "
                "this store",
                key="not_found",
                subject_key="customer_return",
            )

        invoice = await self._live_invoice(document)
        others = await self._returns.find(
            CustomerReturnsForInvoice(document.sales_invoice_id)
        )
        self._assert_nothing_returned_twice(document, invoice, others)
        await self._apply_relief(request, document, invoice, others)

        document.confirm(self._clock.now(), self._current.user_id)
        confirmed_before = [
            other
            for other in others
            if other.id != document.id
            and other.status is DocumentStatus.CONFIRMED
        ]
        await self._poster.take_back(document, invoice, confirmed_before)
        await self._returns.update(document, spec)
        await self._uow.commit()

        return ResultWithData[CustomerReturnData].succeed_with_data(
            CustomerReturnData.from_entity(document)
        )

    async def _live_invoice(self, document: CustomerReturn) -> SalesInvoice:
        invoice = await self._invoices.find_one(
            SalesInvoiceById(document.sales_invoice_id)
        )
        if invoice is None:
            raise NotFoundError(
                f"sales invoice {document.sales_invoice_id} does not exist in this store",
                key="not_found",
                subject_key="sales_invoice",
            )
        # Re-checked here because the sale can be cancelled while a return
        # sits open, and a cancellation already put every unit back.
        if invoice.status is not DocumentStatus.CONFIRMED:
            raise DocumentNotConfirmedError(
                f"{invoice.number} is {invoice.status.value}, so there is no sale to "
                "return against",
                key="return_needs_confirmed_sale",
                number=invoice.number,
            )
        return invoice

    def _assert_nothing_returned_twice(
        self,
        document: CustomerReturn,
        invoice: SalesInvoice,
        others: Sequence[CustomerReturn],
    ) -> None:
        """FR-4.9b, against every *confirmed* return on this sale.

        A draft is deliberately not counted. Two drafts naming the same
        handset is a mistake somebody will fix; refusing the first one to
        reach confirm would make it unfixable.
        """
        standing = [
            other
            for other in others
            if other.id != document.id and other.status is DocumentStatus.CONFIRMED
        ]
        for line in document.lines:
            taken = sum(
                other_line.quantity
                for other in standing
                for other_line in other.lines
                if other_line.sales_invoice_line_id == line.sales_invoice_line_id
            )
            if taken + line.quantity > line.sold_quantity:
                raise AlreadyReturnedError(
                    f"{invoice.number} sold {line.sold_quantity} of this line and "
                    f"{taken} have already come back, so {document.number} cannot "
                    f"take {line.quantity} more",
                    number=document.number,
                    sold=line.sold_quantity,
                    taken=taken,
                )

    async def _apply_relief(
        self,
        request: ConfirmCustomerReturnCommand,
        document: CustomerReturn,
        invoice: SalesInvoice,
        others: Sequence[CustomerReturn],
    ) -> None:
        relief = self._prices.parse(request.debt_relief, Currency.UZS)
        if relief is None:
            return
        if not invoice.payment_type.opens_debt:
            raise DebtReliefError(
                f"{invoice.number} is {invoice.payment_type.value} and was settled at "
                "confirm, so there is no debt for a return to relieve",
                key="relief_not_a_credit_sale",
                number=invoice.number,
            )

        outstanding = remaining_on(
            invoice,
            await self._payments.find(PaymentsForInvoice(invoice.id)),
            [other for other in others if other.id != document.id],
        )
        if relief > outstanding:
            raise DebtReliefError(
                f"{relief.format()} is more than the {outstanding.format()} still "
                f"owed on {invoice.number} — refund the difference instead",
                key="relief_over_balance",
                relief=relief.format(),
                remaining=outstanding.format(),
                number=invoice.number,
            )
        document.debt_relief = relief
