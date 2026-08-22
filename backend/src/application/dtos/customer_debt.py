"""What one customer owes, and who owes the most (PRD §4.7, FR-11.9, FR-11.10).

Read rows, not entities. Both are stitched from ``sales_invoices`` and
``payments`` in a single grouped query, because a balance is
``debt − Σ payments`` and computing that by loading every invoice
aggregate and every payment row into Python would read the store's whole
credit history to answer one question.

Nothing here is stored. ``remaining`` and ``balance`` are recomputed on
every read, which is what makes them impossible to drift: there is no
column anywhere that a bug could leave holding yesterday's figure.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.enums import DocumentStatus, PaymentType
from domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class CreditInvoiceDebt:
    """One non-cash sale on a customer's account.

    Covers both halves of FR-11.9: a ``STORE_CREDIT`` row carries a real
    debt, and a ``CREDIT_COMPANY`` row carries none at all — it appears on
    the account labelled by company and settled, because attributing the
    company's debt to the customer would be the most misleading thing this
    system could do (§4.7).
    """

    invoice_id: UUID
    invoice_number: str
    status: DocumentStatus
    payment_type: PaymentType
    confirmed_at: datetime | None
    # None for a financed sale: it opened no debt.
    debt: Money | None
    paid: Money
    credit_company_id: UUID | None
    contract_ref: str | None

    @property
    def remaining(self) -> Money:
        """What is still owed on this invoice.

        Zero for a financed sale, and zero for a cancelled one: cancelling
        voids the debt (FR-11.11) without touching the payments already
        received, which is why this reads the status rather than the debt
        column alone.
        """
        if self.debt is None or self.status is not DocumentStatus.CONFIRMED:
            return Money.zero(self.paid.currency)
        return self.debt - self.paid

    @property
    def is_open(self) -> bool:
        return not self.remaining.is_zero and not self.remaining.is_negative


@dataclass(frozen=True, slots=True)
class DebtorSummary:
    """One line of the debtor list (FR-11.10).

    ``oldest_open_at`` is what the list sorts on. Store credit has no due
    date by design, so nothing is ever formally overdue — the age of the
    oldest open invoice is what makes a stale debt visible anyway.
    """

    customer_id: UUID
    full_name: str
    phone: str | None
    balance: Money
    oldest_open_at: datetime
    open_invoice_count: int
