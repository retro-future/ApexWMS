"""Recording money received against store credit (PRD §4.7, FR-11.6).

Three handlers need this and they must all behave identically: the confirm
that records a down payment (FR-11.5), the counter recording an
instalment, and the manager compensating a mistake (FR-11.8). Two of them
getting the overpayment rule slightly differently is exactly how a balance
goes negative.

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

from application.dtos import CurrentUser, MoneyEffect
from application.ports import Clock, PaymentRepository
from application.services.ledger import LedgerPoster
from domain.entities import Payment, SalesInvoice
from domain.enums import DocumentStatus, DocumentType, PaymentMethod, TransactionType
from domain.errors import (
    CurrencyMismatchError,
    NotACreditSaleError,
    OverpaymentError,
    PaymentAlreadyReversedError,
)
from domain.value_objects import Currency, Money


class PaymentPoster:
    def __init__(
        self,
        payments: PaymentRepository,
        poster: LedgerPoster,
        clock: Clock,
        current: CurrentUser,
    ) -> None:
        self._payments = payments
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
        """Take money off what *invoice* still owes (FR-11.6)."""
        await self._assert_collectable(invoice, amount)

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
        if await self._payments.reversal_of(original.id) is not None:
            raise PaymentAlreadyReversedError(
                f"payment {original.id} has already been reversed — reversing it "
                "again would re-apply it"
            )

        compensating = original.reversed(self._clock.now(), self._current.user_id)
        await self._append(compensating, invoice)
        return compensating

    async def _append(self, payment: Payment, invoice: SalesInvoice) -> None:
        await self._payments.add(payment)
        await self._poster.post_money(
            DocumentType.PAYMENT,
            payment.id,
            [MoneyEffect(TransactionType.PAYMENT_RECEIVED, payment.amount)],
            location_id=invoice.location_id,
        )

    async def _assert_collectable(self, invoice: SalesInvoice, amount: Money) -> None:
        if not invoice.payment_type.opens_debt or invoice.debt is None:
            raise NotACreditSaleError(
                f"{invoice.number} is {invoice.payment_type.value} and was settled "
                "at confirm, so there is nothing to pay down (FR-11.4)"
            )
        if invoice.status is not DocumentStatus.CONFIRMED:
            raise NotACreditSaleError(
                f"{invoice.number} is {invoice.status.value} and owes nothing — a "
                "cancelled sale's debt is void (FR-11.11)"
            )

        if amount.currency is not Currency.UZS:
            raise CurrencyMismatchError(
                f"a payment of {amount.currency.value} settles nothing — all "
                "customer debt is written in som (§4.7)"
            )

        remaining = invoice.debt - await self._payments.paid_for(invoice.id)
        if amount > remaining:
            raise OverpaymentError(
                f"{amount.format()} is more than the {remaining.format()} still owed "
                f"on {invoice.number}"
            )
