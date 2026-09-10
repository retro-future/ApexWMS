"""Money the store actually received against a sale (PRD §4.7, FR-11.6).

Append-only, like both ledgers and for the same reason: the customer's
balance is *derived* from `(debt entered at sale) − (payments recorded)`,
so a balance you can trust needs rows nobody can go back and edit. **A
mistaken payment is reversed by a compensating negative payment**, which is
what ``reverses_payment_id`` names.

**A payment carries its own currency and converts nothing.** Against a
store-credit debt it is som, because the debt itself is a som figure the
seller wrote at the counter (§4.7) — ``PaymentPoster`` is where that rule
lives, since only it knows the invoice. On a sale settled at confirm the
payment is a *tender*: what the customer physically handed over, in
whatever currency, sitting beside revenue booked in the product's own and
never netted against it.

A payment settles a debt or fills the till; it never books revenue.
``SALE_REVENUE`` was written in full the moment the sale confirmed
(FR-11.7), and re-booking it per instalment is the signature bug of naive
credit systems.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.enums import PaymentMethod
from domain.errors import InvalidMoneyError, PaymentAlreadyReversedError
from domain.value_objects import Money


@dataclass(eq=False, kw_only=True)
class Payment(UuidEntity, TenantEntity):
    sales_invoice_id: UUID
    occurred_at: datetime
    # Signed: negative is a compensating entry against an earlier payment.
    amount: Money
    method: PaymentMethod
    user_id: UUID
    note: str | None = None
    reverses_payment_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.amount.is_zero:
            raise InvalidMoneyError("a payment of zero settles nothing")
        if self.is_reversal and not self.amount.is_negative:
            raise InvalidMoneyError(
                "a reversal gives money back, so its amount is negative (FR-11.8)"
            )
        if not self.is_reversal and self.amount.is_negative:
            raise InvalidMoneyError(
                "a negative payment must name the payment it reverses (FR-11.8)"
            )

    @property
    def is_reversal(self) -> bool:
        return self.reverses_payment_id is not None

    def reversed(self, occurred_at: datetime, user_id: UUID) -> Payment:
        """The compensating entry for this one (FR-11.8).

        The original stays. A reversed payment is *two* rows, not zero,
        because the money really did change hands twice.
        """
        if self.is_reversal:
            raise PaymentAlreadyReversedError(
                "a reversal is not itself reversed — record a fresh payment instead"
            )
        return Payment(
            sales_invoice_id=self.sales_invoice_id,
            occurred_at=occurred_at,
            amount=-self.amount,
            method=self.method,
            user_id=user_id,
            note=f"reversal of payment {self.id}",
            reverses_payment_id=self.id,
        )
