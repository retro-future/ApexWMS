"""How a sale is being paid for (PRD §4.7, FR-11.1).

Three ways a phone leaves the store, and the only thing that separates
them is who — if anyone — still owes the store money afterwards: nobody,
nobody, the customer. The goods and the accrual are identical in all three
cases (FR-11.2), which is why this is a label on the invoice rather than
three document types.

``CREDIT_COMPANY`` carries no financial machinery on purpose: the company
pays in full at sale time, so from the store's side it differs from
``PAID_IN_FULL`` only by naming which company financed it.
"""

from enum import StrEnum


class PaymentType(StrEnum):
    PAID_IN_FULL = "paid_in_full"
    CREDIT_COMPANY = "credit_company"
    STORE_CREDIT = "store_credit"

    @property
    def opens_debt(self) -> bool:
        """Whether confirming this sale leaves the customer owing the store."""
        return self is PaymentType.STORE_CREDIT
