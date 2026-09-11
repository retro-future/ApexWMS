"""Recording money the store actually received (PRD §4.7, FR-11.6).

Three handlers need this and they must all behave identically: the confirm
that records a down payment (FR-11.5), the counter recording an
instalment, and the manager compensating a mistake (FR-11.8). Two of them
getting the overpayment rule slightly differently is exactly how a balance
goes negative.

Two kinds of money arrive here and the invoice decides which. Against a
store-credit debt it is a **payment**: som, capped at what is still owed,
booked as ``PAYMENT_RECEIVED``. On a sale the customer settled at the
counter it is a **tender**: whatever they physically handed over, in
whatever currency, booked as ``TENDER_RECEIVED``. A tender has nothing to
be capped against — the sale owes nothing — and is never netted against the
revenue beside it, which is in the product's own currency and stays there.

A tender is recorded for every store, not only one that balances a drawer
(W9 B1): a dollar-priced handset paid for in som leaves no som figure
anywhere else, and a figure not written down today cannot be recovered
later. ``tenant_settings.runs_till`` still gates the *shift* screens that
prove a drawer, and the trade-in payout on the receipt side.

A credit-company sale takes neither. The company settles with the store
outside this system (§4.7), so nothing changes hands at the counter and
there is no row to write.

**A payment never books revenue.** Only ``PAYMENT_RECEIVED`` is written
here, and ``SALE_REVENUE`` is booked once, at confirm, by ``InvoicePoster``
(FR-11.7). Re-booking revenue per instalment is the signature bug of naive
credit systems, and keeping the two in separate services is what makes it
impossible rather than merely unlikely.

The ledger row names ``(PAYMENT, payment.id)`` rather than the invoice, so
cancelling a store-credit sale reverses its revenue and COGS and leaves the
money the customer actually handed over untouched (FR-11.11).

Nothing here commits — the calling handler owns the transaction, like every
other poster.
"""

from collections.abc import Sequence

from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from application.common.specification import Specification
from application.dtos import CurrentUser, MoneyEffect
from application.ports import Clock
from application.services.customer_balance import remaining_on
from application.services.ledger import LedgerPoster
from application.specs import CustomerReturnsForInvoice, PaymentsForInvoice
from domain.entities import CustomerReturn, Payment, SalesInvoice
from domain.enums import (
    DocumentStatus,
    DocumentType,
    PaymentMethod,
    PaymentType,
    TransactionType,
)
from domain.errors import (
    CurrencyMismatchError,
    NotACreditSaleError,
    OverpaymentError,
    PaymentAlreadyReversedError,
    TenderAlreadyRecordedError,
    TenderExceedsSaleError,
)
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import CustomerReturnModel, PaymentModel


class PaymentPoster:
    def __init__(
        self,
        payments: TenantAppendOnlyRepository[Payment, PaymentModel],
        returns: TenantDbRepository[CustomerReturn, CustomerReturnModel],
        poster: LedgerPoster,
        clock: Clock,
        current: CurrentUser,
    ) -> None:
        self._payments = payments
        self._returns = returns
        self._poster = poster
        self._clock = clock
        self._current = current

    async def receive(
        self,
        invoice: SalesInvoice,
        amount: Money,
        method: PaymentMethod = PaymentMethod.CASH,
        note: str | None = None,
    ) -> Payment:
        """Take money off what *invoice* still owes, or into the till.

        A store-credit sale takes a payment against its debt; a sale settled
        at the counter takes a tender, which only records what changed hands.
        """
        if invoice.payment_type.opens_debt:
            await self._assert_collectable(invoice, amount)
        else:
            await self._assert_tenderable(invoice, amount)

        payment = Payment(
            sales_invoice_id=invoice.id,
            occurred_at=self._clock.now(),
            amount=amount,
            method=method,
            user_id=self._current.user_id,
            note=note,
        )
        await self._append(payment, invoice)
        return payment

    async def reverse(self, original: Payment, invoice: SalesInvoice) -> Payment:
        """Compensate a payment that should not have been recorded (FR-11.8).

        The original stays. A reversed payment is two rows, not zero,
        because a mistake is part of the history.
        """
        reversal = Specification(PaymentModel).where(
            PaymentModel.reverses_payment_id == original.id
        )
        if await self._payments.find_one(reversal) is not None:
            raise PaymentAlreadyReversedError(
                f"payment {original.id} has already been reversed — reversing it "
                "again would re-apply it"
            )

        compensating = original.reversed(self._clock.now(), self._current.user_id)
        await self._append(compensating, invoice)
        return compensating

    async def _append(self, payment: Payment, invoice: SalesInvoice) -> None:
        await self._payments.add(payment)
        category = (
            TransactionType.PAYMENT_RECEIVED
            if invoice.payment_type.opens_debt
            else TransactionType.TENDER_RECEIVED
        )
        await self._poster.post_money(
            DocumentType.PAYMENT,
            payment.id,
            [MoneyEffect(category, payment.amount)],
            location_id=invoice.location_id,
        )

    async def _assert_tenderable(self, invoice: SalesInvoice, amount: Money) -> None:
        """A tender records money over the counter, so there has to be one.

        And one per currency. Half in dollars and half in som is a real way
        to settle a sale, but a second row in a currency already recorded is
        not: nothing caps a tender, so it would silently double what the
        sale is said to have taken. Correcting one is a reversal.

        The amount is capped only where the sale is priced in that one
        currency, which needs no rate. See ``_sole_total``.
        """
        if invoice.payment_type is not PaymentType.PAID_IN_FULL:
            raise NotACreditSaleError(
                f"{invoice.number} is {invoice.payment_type.value}: the company "
                "settles with the store, so nothing crosses the counter (FR-11.4)",
                key="not_a_credit_sale",
                number=invoice.number,
            )
        if invoice.status is not DocumentStatus.CONFIRMED:
            raise NotACreditSaleError(
                f"{invoice.number} is {invoice.status.value}; money changes hands "
                "on a confirmed sale",
                key="sale_not_confirmed",
                number=invoice.number,
            )
        charged = self._sole_total(invoice, amount.currency)
        if charged is not None and amount > charged:
            raise TenderExceedsSaleError(
                f"{amount.format()} is more than the {charged.format()} "
                f"{invoice.number} charges in that currency",
                amount=amount.format(),
                charged=charged.format(),
                number=invoice.number,
            )
        recorded = await self._payments.find(PaymentsForInvoice(invoice.id))
        if amount.currency in self._standing_currencies(recorded):
            raise TenderAlreadyRecordedError(
                f"{invoice.number} already records "
                f"{amount.currency.value} taken over the counter. Reverse "
                "that row before recording another.",
                key="tender_already_recorded",
                number=invoice.number,
                currency=amount.currency.value,
            )

    @staticmethod
    def _sole_total(invoice: SalesInvoice, currency: Currency) -> Money | None:
        """What the sale charges, when it charges in *currency* and nothing else.

        On a mixed sale there is nothing to compare against without a rate:
        a customer can settle a dollar handset and a som case together in
        either currency, so any column would refuse a real payment.
        """
        subtotals = invoice.subtotals()
        if set(subtotals) != {currency}:
            return None
        return subtotals[currency]

    @staticmethod
    def _standing_currencies(payments: Sequence[Payment]) -> set[Currency]:
        """The currencies whose rows have not been reversed away."""
        undone = {
            payment.reverses_payment_id
            for payment in payments
            if payment.reverses_payment_id is not None
        }
        return {
            payment.amount.currency
            for payment in payments
            if not payment.is_reversal and payment.id not in undone
        }

    async def _assert_collectable(self, invoice: SalesInvoice, amount: Money) -> None:
        if invoice.debt is None:
            raise NotACreditSaleError(
                f"{invoice.number} opened no debt, so there is nothing to pay "
                "down (FR-11.4)",
                key="not_a_credit_sale",
                number=invoice.number,
            )
        if invoice.status is not DocumentStatus.CONFIRMED:
            raise NotACreditSaleError(
                f"{invoice.number} is {invoice.status.value} and owes nothing — a "
                "cancelled sale's debt is void (FR-11.11)",
                key="debt_already_void",
                number=invoice.number,
            )

        if amount.currency is not Currency.UZS:
            raise CurrencyMismatchError(
                f"a payment of {amount.currency.value} settles nothing — all "
                "customer debt is written in som (§4.7)",
                key="payment_not_som",
            )

        # Through ``remaining_on`` rather than a subtraction here, so the
        # relief a customer return already wrote off cannot be paid twice
        # (FR-4.9d).
        remaining = remaining_on(
            invoice,
            await self._payments.find(PaymentsForInvoice(invoice.id)),
            await self._returns.find(CustomerReturnsForInvoice(invoice.id)),
        )
        if amount > remaining:
            raise OverpaymentError(
                f"{amount.format()} is more than the {remaining.format()} still owed "
                f"on {invoice.number}",
                amount=amount.format(),
                remaining=remaining.format(),
                number=invoice.number,
            )
