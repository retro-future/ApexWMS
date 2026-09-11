"""Reading a dollar figure in som at the rate of the day it happened (W9 B3).

Built from the whole rate log at once rather than asked a row at a time,
because a month-end report converts hundreds of daily figures and every one
of them would otherwise be a query.

Two rules worth stating. A day with no rate of its own takes the most
recent earlier one, which is what a store does anyway between quotes. A day
before the log starts takes the *earliest* rate ever quoted, and the report
says so: the alternative is no som column at all for every month the store
traded before it began recording rates.
"""

from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from domain.entities import ExchangeRate
from domain.errors import CurrencyMismatchError
from domain.value_objects import Currency, Money


class SomConverter:
    def __init__(self, rates: Sequence[ExchangeRate]) -> None:
        # One row per day, the last one quoted for it, oldest first.
        by_day: dict[date, Decimal] = {}
        for rate in sorted(rates, key=lambda one: (one.effective_on, one.set_at)):
            by_day[rate.effective_on] = rate.som_per_usd
        self._days = sorted(by_day)
        self._by_day = by_day

    @property
    def is_empty(self) -> bool:
        return not self._days

    @property
    def starts_on(self) -> date:
        """The earliest day the log has a rate for."""
        return self._days[0]

    def on(self, day: date) -> Decimal:
        """The rate in force on *day*, the earliest one before the log."""
        in_force = [quoted for quoted in self._days if quoted <= day]
        return self._by_day[in_force[-1] if in_force else self._days[0]]

    def convert(self, amount: Money, day: date) -> Money:
        """*amount* in som, rounded to whole som, half up.

        Som passes through untouched. Any other currency is refused rather
        than guessed at: the log holds one pair, som per dollar.
        """
        if amount.currency is Currency.UZS:
            return amount
        if amount.currency is not Currency.USD:
            raise CurrencyMismatchError(
                f"no rate is recorded for {amount.currency.value}, only for dollars"
            )
        major = Decimal(amount.amount_minor) / Decimal(10**Currency.USD.exponent)
        som = (major * self.on(day)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return Money(int(som), Currency.UZS)
