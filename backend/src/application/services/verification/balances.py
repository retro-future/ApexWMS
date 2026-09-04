"""§4.7: every customer balance recomputed from the rows behind it.

The service behind ``apexwms verify-balances`` (FR-10.7b). Customer
balances are *always* derived, so there is no cached projection to check
them against — what this audits instead is that the two independent
records of the same fact agree: the ``payments`` table and the money
ledger's ``PAYMENT_RECEIVED`` rows.

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
from domain.enums import TransactionType
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
            invoice = await self._invoices.find_one(SalesInvoiceById(invoice_id))
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
            relieved = relieved_on(
                await self._returns.find(CustomerReturnsForInvoice(invoice.id))
            )
            settled = paid + relieved
            if settled > invoice.debt:
                found.append(
                    Discrepancy(
                        subject=f"debt on {invoice.number}",
                        expected=(
                            f"at least the {settled.format()} collected and relieved"
                        ),
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
