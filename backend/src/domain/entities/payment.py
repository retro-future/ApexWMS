"""Money received against a store-credit sale (PRD §4.7, FR-11.6).

Append-only, like both ledgers and for the same reason: the customer's
balance is *derived* from `(debt entered at sale) − (payments recorded)`,
so a balance you can trust needs rows nobody can go back and edit. **A
mistaken payment is reversed by a compensating negative payment**, which is
what ``reverses_payment_id`` names.

Always in som, whatever currency the handset was priced in. The seller
writes the total som figure at the counter and *that figure is the debt* —
there is no rate here and no conversion (§4.7).

A payment settles a debt; it never books revenue. ``SALE_REVENUE`` was
written in full the moment the sale confirmed (FR-11.7), and re-booking it
per instalment is the signature bug of naive credit systems.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.enums import PaymentMethod
from domain.errors import CurrencyMismatchError, InvalidMoneyError
from domain.value_objects import Currency, Money


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
        if self.amount.currency is not Currency.UZS:
            raise CurrencyMismatchError(
                f"a payment is {self.amount.currency.value} but all customer debt "
                "is written in som (§4.7)"
            )
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
            raise InvalidMoneyError(
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
