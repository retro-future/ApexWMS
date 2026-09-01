"""FR-4.6 and FR-11.1: confirming the sale, on whatever terms it was struck.

The invoice decides what it can decide — that it is still a draft, that it
has lines, that no handset is on it twice, that its payment terms hang
together — and ``InvoicePoster`` does the rest, because re-resolving a
price needs the live unit and the live catalog row (FR-4.5b1).

**The phone leaves on every payment type** (FR-11.2). Stock moves and the
full ``SALE_REVENUE``/``COGS`` is booked in the product's own currency
whether the customer paid, a credit company paid, or nobody has paid yet.
The only difference between the three is who still owes the store money
afterwards: nobody, nobody, the customer.

A store-credit confirm records its down payment as an ordinary first
``Payment`` (FR-11.5) rather than netting it off the debt. That is what
makes ``remaining = debt − Σ payments`` hold with no special case, and it
is why the down payment turns up in "cash collected" like any other.

This handler owns the transaction, and that is what makes FR-4.5b2 true: a
line that has stopped resolving raises from the poster, the transaction
rolls back, and **nothing reaches either ledger** — not the lines that
resolved fine before it, not the movement for the phone already marked
sold in memory, and not the down payment.
"""

from uuid import UUID

from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import SalesInvoiceData
from application.ports import (
    Clock,
    TenantUnitOfWork,
)
from application.services import (
    BelowCostChecker,
    InvoicePoster,
    PaymentPoster,
    SalePriceParser,
)
from application.specs import PaymentsForInvoice, SalesInvoiceForWrite
from domain.entities import CreditCompany, Payment, SalesInvoice
from domain.enums import PaymentMethod, PaymentType
from domain.errors import CreditTermsError
from domain.value_objects import Currency
from infrastructure.persistence.tenant.models import (
    CreditCompanyModel,
    PaymentModel,
    SalesInvoiceModel,
)


class ConfirmSalesInvoiceCommandPayload(CamelModel):
    """The terms the sale is actually struck on, stated at the counter.

    Omitted entirely, the invoice confirms on whatever it already carries —
    ``PAID_IN_FULL`` unless the draft said otherwise (FR-11.1).
    """

    payment_type: PaymentType | None = None
    credit_company_id: UUID | None = None
    contract_ref: str | None = None
    # Som, as a major-unit string or int — never a JSON float (§4.5).
    debt: str | int | None = None
    down_payment: str | int | None = None
    payment_method: PaymentMethod = PaymentMethod.CASH


class ConfirmSalesInvoiceCommand(
    ConfirmSalesInvoiceCommandPayload, Command[ResultWithData[SalesInvoiceData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    sales_invoice_id: UUID


class ConfirmSalesInvoiceHandler(
    IRequestHandler[ResultWithData[SalesInvoiceData], ConfirmSalesInvoiceCommand]
):
    def __init__(
        self,
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        companies: TenantDbRepository[CreditCompany, CreditCompanyModel],
        payments: TenantAppendOnlyRepository[Payment, PaymentModel],
        poster: InvoicePoster,
        payment_poster: PaymentPoster,
        prices: SalePriceParser,
        checker: BelowCostChecker,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._invoices = invoices
        self._companies = companies
        self._payments = payments
        self._poster = poster
        self._payment_poster = payment_poster
        self._prices = prices
        self._checker = checker
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: ConfirmSalesInvoiceCommand
    ) -> ResultWithData[SalesInvoiceData]:
        spec = SalesInvoiceForWrite(request.sales_invoice_id)
        invoice = await self._invoices.find_one(spec)
        if invoice is None:
            raise NotFoundError(
                f"invoice {request.sales_invoice_id} does not exist in this store",
                key="not_found",
                subject_key="invoice",
            )
        await self._apply_terms(invoice, request)

        invoice.confirm(self._clock.now(), self._current.user_id)
        # Read the pool before the sale drains it: the figure is "what these
        # cost going in", the same basis the goods-receipt warning uses.
        alerts = await self._checker.alerts_for_invoice(invoice)
        await self._poster.sell(invoice)
        await self._take_down_payment(invoice, request)
        await self._invoices.update(invoice, spec)
        await self._uow.commit()

        return ResultWithData[SalesInvoiceData].succeed_with_data(
            SalesInvoiceData.from_entity(
                invoice,
                await self._payments.find(PaymentsForInvoice(invoice.id)),
                below_cost_alerts=alerts,
            )
        )

    async def _apply_terms(
        self, invoice: SalesInvoice, request: ConfirmSalesInvoiceCommand
    ) -> None:
        if request.payment_type is None:
            return

        if request.payment_type is PaymentType.CREDIT_COMPANY:
            await self._assert_company_available(request.credit_company_id)

        invoice.set_terms(
            request.payment_type,
            credit_company_id=request.credit_company_id,
            contract_ref=request.contract_ref,
            debt=self._prices.parse(request.debt, Currency.UZS),
        )

    async def _assert_company_available(self, company_id: UUID | None) -> None:
        if company_id is None:
            # Left to the entity, which states the same rule for a draft
            # that was saved this way and never re-stated at confirm.
            return
        company = await self._companies.get(company_id)
        if company is None:
            raise NotFoundError(
                "no such credit company in this store",
                key="not_found",
                subject_key="credit_company",
            )
        if not company.is_active:
            raise CreditTermsError(
                f"{company.name} is no longer a financing partner of this store"
            )

    async def _take_down_payment(
        self, invoice: SalesInvoice, request: ConfirmSalesInvoiceCommand
    ) -> None:
        down = self._prices.parse(request.down_payment, Currency.UZS)
        if down is None or down.is_zero:
            return
        await self._payment_poster.receive(
            invoice, down, request.payment_method, "down payment"
        )
