"""The money ledger's vocabulary (PRD §4.6) — the categories the month-end
report groups by.

``ordinary_sign`` records which way each category points when it is first
booked: a purchase takes money out, revenue brings it in. It is
deliberately **not** an invariant on ``FinancialTransaction``, because
cancelling a document writes *reversing* transactions (§4.6 rule 2, FR-10.2)
— a reversed ``PURCHASE`` is a positive row of the same category, and must
be, so that summing the category still nets to zero for a cancelled
document.

The one category with no ordinary direction is ``COUNT_ADJUSTMENT``: a
physical count finds surplus as readily as shortage, and neither is the
exceptional case.

**Revenue is not cash.** ``SALE_REVENUE`` is booked in full the moment a
sale is confirmed, paid or not (accrual), while ``PAYMENT_RECEIVED``
settles the debt that sale opened. A payment must never write revenue, or
every store-credit instalment would inflate the books — see §4.6's box.
"""

from enum import StrEnum


class TransactionType(StrEnum):
    PURCHASE = "purchase"
    SALE_REVENUE = "sale_revenue"
    COGS = "cogs"
    WRITE_OFF_LOSS = "write_off_loss"
    SUPPLIER_RETURN_CREDIT = "supplier_return_credit"
    COUNT_ADJUSTMENT = "count_adjustment"
    PAYMENT_RECEIVED = "payment_received"

    @property
    def ordinary_sign(self) -> int:
        """+1, -1, or 0 where the category genuinely goes both ways.

        Describes the *first* posting only. A reversal negates it.
        """
        return _ORDINARY_SIGN[self]


_ORDINARY_SIGN: dict[TransactionType, int] = {
    TransactionType.PURCHASE: -1,
    TransactionType.SALE_REVENUE: +1,
    TransactionType.COGS: -1,
    TransactionType.WRITE_OFF_LOSS: -1,
    TransactionType.SUPPLIER_RETURN_CREDIT: +1,
    TransactionType.COUNT_ADJUSTMENT: 0,
    TransactionType.PAYMENT_RECEIVED: +1,
}
