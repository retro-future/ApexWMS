"""§4.7: every customer balance recomputed from the rows behind it.

The service behind ``apexwms verify-balances`` (FR-10.7b). Customer
balances are *always* derived, so there is no cached projection to check
them against — what this audits instead is that the two independent
records of the same fact agree: the ``payments`` table and the money
ledger's ``PAYMENT_RECEIVED`` and ``TENDER_RECEIVED`` rows.

Payments are grouped **per invoice and per currency**, never summed across
currencies. A sale settled at the counter may take a dollar tender and a som
one, and adding those is the arithmetic the whole money model exists to
prevent (§4.5 rule 1).

The negative-balance sweep counts customer-return relief alongside the
payments (FR-4.9d). Without it a fully returned credit sale reads as
overpaid, and the audit would report a discrepancy on every one of them.
"""

from uuid import UUID

from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from application.common.specification import Specification
from application.dtos import Discrepancy
from application.ports import FinancialTransactionQueries
from application.services.customer_balance import relieved_on
from application.specs import CustomerReturnsForInvoice, SalesInvoiceById
from domain.entities import CustomerReturn, Payment, SalesInvoice
from domain.enums import PaymentType, TransactionType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    CustomerReturnModel,
    PaymentModel,
    SalesInvoiceModel,
)


class BalanceVerifier:
    """§4.7: every customer balance recomputed from the rows behind it."""

    def __init__(
        self,
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        payments: TenantAppendOnlyRepository[Payment, PaymentModel],
        returns: TenantDbRepository[CustomerReturn, CustomerReturnModel],
        transactions: FinancialTransactionQueries,
    ) -> None:
        self._invoices = invoices
        self._payments = payments
        self._returns = returns
        self._transactions = transactions

    async def verify(self) -> list[Discrepancy]:
        """A mismatch is reported, never repaired.

        Rewriting a debt to match the payments would destroy the evidence
        of whatever wrote it wrong — and this is the one sweep whose
        findings are somebody's money.
        """
        payments = list(
            await self._payments.find(
                Specification(PaymentModel).order(
                    PaymentModel.occurred_at, PaymentModel.id
                )
            )
        )
        return [
            *await self._verify_invoices(payments),
            *await self._verify_ledger_agrees(payments),
        ]

    async def _verify_invoices(self, payments: list[Payment]) -> list[Discrepancy]:
        """Each invoice's terms against what has been collected on it.

        Three bugs, all worth catching: a store-credit sale paid past its
        debt (the balance has gone negative), a debt settled in anything but
        som (§4.7), and a credit-company sale carrying money at all — the
        company settles with the store, so nothing crosses the counter.

        A tender on a ``PAID_IN_FULL`` sale is none of those. It is expected,
        in whatever currency, and capped by nothing: the sale owes nothing to
        overpay.
        """
        collected: dict[UUID, dict[Currency, Money]] = {}
        for payment in payments:
            by_currency = collected.setdefault(payment.sales_invoice_id, {})
            currency = payment.amount.currency
            by_currency[currency] = (
                by_currency.get(currency, Money.zero(currency)) + payment.amount
            )

        found: list[Discrepancy] = []
        for invoice_id, totals in collected.items():
            invoice = await self._invoices.find_one(SalesInvoiceById(invoice_id))
            if invoice is None:
                found += [
                    Discrepancy(
                        subject=f"payments against invoice {invoice_id}",
                        expected="an invoice to settle",
                        found=f"{paid.format()} collected against no invoice",
                    )
                    for paid in totals.values()
                ]
                continue
            if invoice.debt is None:
                found += self._verify_no_debt(invoice, totals)
            else:
                found += await self._verify_debt(invoice, totals)
        return found

    @staticmethod
    def _verify_no_debt(
        invoice: SalesInvoice, totals: dict[Currency, Money]
    ) -> list[Discrepancy]:
        """A sale that opened no debt. Only a paid-in-full one may hold money."""
        if invoice.payment_type is PaymentType.PAID_IN_FULL:
            return []
        return [
            Discrepancy(
                subject=f"money against {invoice.number}",
                expected=f"none — it is {invoice.payment_type.value}",
                found=paid.format(),
            )
            for paid in totals.values()
        ]

    async def _verify_debt(
        self, invoice: SalesInvoice, totals: dict[Currency, Money]
    ) -> list[Discrepancy]:
        assert invoice.debt is not None
        found = [
            Discrepancy(
                subject=f"debt on {invoice.number}",
                expected="som — all customer debt is written in som (§4.7)",
                found=paid.format(),
            )
            for currency, paid in totals.items()
            if currency is not Currency.UZS
        ]
        paid = totals.get(Currency.UZS, Money.zero(Currency.UZS))
        relieved = relieved_on(
            await self._returns.find(CustomerReturnsForInvoice(invoice.id))
        )
        settled = paid + relieved
        if settled > invoice.debt:
            found.append(
                Discrepancy(
                    subject=f"debt on {invoice.number}",
                    expected=f"at least the {settled.format()} collected and relieved",
                    found=invoice.debt.format(),
                )
            )
        return found

    async def _verify_ledger_agrees(self, payments: list[Payment]) -> list[Discrepancy]:
        """The ``payments`` table against the money ledger.

        Both are written in one transaction by ``PaymentPoster``, so they
        can only disagree if something wrote one without the other — which
        is precisely the bug a sweep exists to find.
        """
        recorded: dict[Currency, Money] = {}
        for payment in payments:
            currency = payment.amount.currency
            recorded[currency] = (
                recorded.get(currency, Money.zero(currency)) + payment.amount
            )

        totals = await self._transactions.totals_by_type()
        # Both categories, because the poster writes one row per payment and
        # picks the category from the invoice: a debt payment and a tender
        # are the same table row and must both be accounted for.
        found = []
        for currency in Currency:
            booked = Money.zero(currency)
            for category in (
                TransactionType.PAYMENT_RECEIVED,
                TransactionType.TENDER_RECEIVED,
            ):
                booked = booked + totals.get(
                    (category, currency), Money.zero(currency)
                )
            mine = recorded.get(currency, Money.zero(currency))
            if mine != booked:
                found.append(
                    Discrepancy(
                        subject=f"money received, {currency.value}",
                        expected=booked.format(),
                        found=mine.format(),
                    )
                )
        return found
