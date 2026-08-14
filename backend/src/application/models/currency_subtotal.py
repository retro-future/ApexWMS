"""One document total, in one currency — PRD §4.5 rule 4, FR-2.7.

A document may hold lines in both currencies, and it presents **one
subtotal per currency present, never their sum**. That is why this is a
list of these rather than a single ``total`` field: there is no field for
a combined figure to be written into, so no future caller can add
500 cents to 30 000 som and get a number.
"""

from __future__ import annotations

from decimal import Decimal

from application.core import CamelModel
from domain.value_objects import Currency, Money


class CurrencySubtotalData(CamelModel):
    currency: Currency
    amount: Decimal
    amount_minor: int

    @classmethod
    def from_entity(cls, totals: dict[Currency, Money]) -> list[CurrencySubtotalData]:
        return [
            cls(
                currency=currency,
                amount=amount.as_major(),
                amount_minor=amount.amount_minor,
            )
            for currency, amount in sorted(totals.items(), key=lambda pair: pair[0].value)
        ]
