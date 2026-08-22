"""§4.7: every customer balance recomputed from the rows behind it.

The service behind ``apexwms verify-balances`` (FR-10.7b). Customer
balances are *always* derived, so there is no cached projection to check
them against — what this audits instead is that the two independent
records of the same fact agree: the ``payments`` table and the money
ledger's ``PAYMENT_RECEIVED`` rows.
"""

from uuid import UUID

from application.ports import (
    FinancialTransactionRepository,
    PaymentRepository,
    SalesInvoiceRepository,
)
from application.services.verification.discrepancy import Discrepancy
from domain.entities import Payment
from domain.enums import TransactionType
from domain.value_objects import Currency, Money


class BalanceVerifier:
    """§4.7: every customer balance recomputed from the rows behind it."""

    def __init__(
        self,
        invoices: SalesInvoiceRepository,
        payments: PaymentRepository,
        transactions: FinancialTransactionRepository,
    ) -> None:
        self._invoices = invoices
        self._payments = payments
        self._transactions = transactions

    async def verify(self) -> list[Discrepancy]:
        """A mismatch is reported, never repaired.

        Rewriting a debt to match the payments would destroy the evidence
        of whatever wrote it wrong — and this is the one sweep whose
        findings are somebody's money.
        """
        payments = await self._payments.list_all()
        return [
            *await self._verify_invoices(payments),
            *await self._verify_ledger_agrees(payments),
        ]

    async def _verify_invoices(self, payments: list[Payment]) -> list[Discrepancy]:
        """Each invoice's terms against what has been collected on it.

        Two different bugs, both worth catching: a store-credit sale paid
        past its debt (the balance has gone negative), and a settled sale
        carrying a debt or a payment at all — FR-11.4's "creates no debt
        anywhere" as a sweep rather than a single test.
        """
        collected: dict[UUID, Money] = {}
        for payment in payments:
            _accumulate_for(collected, payment.sales_invoice_id, payment.amount)

        found: list[Discrepancy] = []
        for invoice_id, paid in collected.items():
            invoice = await self._invoices.get(invoice_id)
            if invoice is None:
                found.append(
                    Discrepancy(
                        subject=f"payments against invoice {invoice_id}",
                        expected="an invoice to settle",
                        found=f"{paid.format()} collected against no invoice",
                    )
                )
                continue
            if not invoice.payment_type.opens_debt or invoice.debt is None:
                found.append(
                    Discrepancy(
                        subject=f"payments against {invoice.number}",
                        expected=f"none — it is {invoice.payment_type.value}",
                        found=paid.format(),
                    )
                )
                continue
            if paid > invoice.debt:
                found.append(
                    Discrepancy(
                        subject=f"debt on {invoice.number}",
                        expected=f"at least the {paid.format()} collected",
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
        recorded = Money.zero(Currency.UZS)
        for payment in payments:
            recorded = recorded + payment.amount

        totals = await self._transactions.totals_by_type()
        booked = totals.get(
            (TransactionType.PAYMENT_RECEIVED, Currency.UZS), Money.zero(Currency.UZS)
        )
        if recorded == booked:
            return []
        return [
            Discrepancy(
                subject="cash collected on store credit",
                expected=booked.format(),
                found=recorded.format(),
            )
        ]


def _accumulate_for(totals: dict[UUID, Money], key: UUID, amount: Money) -> None:
    running = totals.get(key)
    totals[key] = amount if running is None else running + amount
