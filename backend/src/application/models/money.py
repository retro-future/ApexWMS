"""The wire shape of one ``Money`` — PRD §4.5.

An amount and its currency travel as one object so a caller cannot pair the
wrong currency with an amount. The major-unit rendering is deliberately not
sent: the two currencies do not share an exponent, so a client that knows
the exponent can derive it and one that does not would be guessing.
"""

from __future__ import annotations

from typing import overload

from application.core import CamelModel
from domain.value_objects import Currency, Money


class MoneyData(CamelModel):
    minor: int
    currency: Currency

    @overload
    @classmethod
    def from_entity(cls, amount: Money) -> MoneyData: ...

    @overload
    @classmethod
    def from_entity(cls, amount: None) -> None: ...

    @overload
    @classmethod
    def from_entity(cls, amount: dict[Currency, Money]) -> list[MoneyData]: ...

    @classmethod
    def from_entity(
        cls, amount: Money | dict[Currency, Money] | None
    ) -> MoneyData | list[MoneyData] | None:
        """One amount, or a whole set of per-currency totals.

        The dict form returns a list because §4.5 rule 4 leaves no field a
        combined cross-currency total could be written into.
        """
        if amount is None:
            return None
        if isinstance(amount, dict):
            return [
                cls(minor=total.amount_minor, currency=currency)
                for currency, total in sorted(amount.items(), key=lambda pair: pair[0].value)
            ]
        return cls(minor=amount.amount_minor, currency=amount.currency)
