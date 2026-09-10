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

from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from application.common.specification import Specification
from application.dtos import CurrentUser, MoneyEffect
from application.ports import Clock, TenantSettingsRepository
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
        settings: TenantSettingsRepository,
    ) -> None:
        self._payments = payments
        self._returns = returns
        self._poster = poster
        self._clock = clock
        self._current = current
        self._settings = settings

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
            await self._assert_tenderable(invoice)

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

    async def _assert_tenderable(self, invoice: SalesInvoice) -> None:
        """A tender records money over the counter, so there has to be one."""
        if not await self._settings.runs_till():
            raise NotACreditSaleError(
                f"{invoice.number} owes nothing, and this store does not run a "
                "till — there is nowhere to record what changed hands",
                key="till_not_kept",
                number=invoice.number,
            )
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
