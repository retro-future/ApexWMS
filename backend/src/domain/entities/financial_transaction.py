"""The money ledger (PRD §4.6).

The stock ledger answers *"what happened to the goods?"* and cannot answer
*"what happened to the money?"* — ten phones received and ten phones
received at double the cost look identical in units. So money gets its own
append-only ledger, on exactly the same principles: nothing records money
except by writing a transaction, transactions are immutable, and every one
names its cause and its author.

**Every aggregate over this ledger is grouped by currency.** A
``SUM(amount_minor)`` without a ``GROUP BY currency`` adds cents to som,
which is why the amount here is a ``Money`` and not an int: cross-currency
arithmetic raises rather than quietly producing a number.

The direction is the **sign of the amount**, not a separate column. A
reversal is the negation of what it reverses (§4.6 rule 2), so with one
signed field a cancelled document's category nets to zero by construction;
with an amount and a direction stored apart, the two can contradict.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.enums import DocumentType, TransactionType
from domain.errors import InvalidMoneyError
from domain.value_objects import Currency, Money


@dataclass(eq=False, kw_only=True)
class FinancialTransaction(UuidEntity, TenantEntity):
    occurred_at: datetime
    txn_type: TransactionType
    # Signed, in the product's own currency — never converted (§4.5 rule 1).
    amount: Money
    document_type: DocumentType
    document_id: UUID
    location_id: UUID | None = None
    product_id: UUID | None = None
    device_unit_id: UUID | None = None
    user_id: UUID
    note: str | None = None

    def __post_init__(self) -> None:
        if self.amount.is_zero:
            raise InvalidMoneyError(
                "a transaction of zero records nothing — the ledger holds what moved"
            )

    @property
    def currency(self) -> Currency:
        return self.amount.currency

    def reversed(self, occurred_at: datetime, user_id: UUID) -> FinancialTransaction:
        """The reversing entry for this one (§4.6 rule 2, FR-10.2).

        The original stays in the ledger; both are visible, and the pair
        nets to zero.
        """
        return FinancialTransaction(
            occurred_at=occurred_at,
            txn_type=self.txn_type,
            amount=-self.amount,
            document_type=self.document_type,
            document_id=self.document_id,
            location_id=self.location_id,
            product_id=self.product_id,
            device_unit_id=self.device_unit_id,
            user_id=user_id,
            note=f"reversal of transaction {self.id}",
        )
