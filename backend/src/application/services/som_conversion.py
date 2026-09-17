"""Reading a dollar figure in som at the rate in force when it happened (W9 B3).

A quote is in force from the moment it was set, so a rate corrected at
noon leaves the morning's figures on the morning's rate. A quote entered
for another day (yesterday's, after the fact, or tomorrow's, in advance)
counts from the start of that day instead. Before the first quote the
earliest rate applies, and the report says so.
"""

from bisect import bisect_right
from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from domain.entities import ExchangeRate
from domain.errors import CurrencyMismatchError
from domain.value_objects import Currency, Money


class SomConverter:
    def __init__(self, rates: Sequence[ExchangeRate], timezone: str) -> None:
        zone = ZoneInfo(timezone)
        # Two quotes starting at the same instant: the later entry wins.
        in_force: dict[datetime, tuple[datetime, Decimal]] = {}
        for rate in rates:
            since = self._in_force_from(rate, zone)
            held = in_force.get(since)
            if held is None or rate.set_at > held[0]:
                in_force[since] = (rate.set_at, rate.som_per_usd)
        self._changes = sorted(in_force)
        self._rates = [in_force[since][1] for since in self._changes]

    @property
    def is_empty(self) -> bool:
        return not self._changes

    @property
    def rate_changes(self) -> list[datetime]:
        """Every instant the rate in force changed, oldest first, in UTC."""
        return list(self._changes)

    def before_the_first_quote(self, at: datetime | None) -> bool:
        """``None`` stands for a figure a query placed before every change."""
        return at is None or at < self._changes[0]

    def on(self, at: datetime | None) -> Decimal:
        """The rate in force at *at*, the earliest one before the log."""
        if at is None:
            return self._rates[0]
        index = bisect_right(self._changes, at) - 1
        return self._rates[max(index, 0)]

    def convert(self, amount: Money, at: datetime | None) -> Money:
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
        som = (major * self.on(at)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return Money(int(som), Currency.UZS)

    @staticmethod
    def _in_force_from(rate: ExchangeRate, zone: ZoneInfo) -> datetime:
        day_start = datetime.combine(rate.effective_on, time(), zone)
        day_end = datetime.combine(rate.effective_on + timedelta(days=1), time(), zone)
        if day_start <= rate.set_at < day_end:
            return rate.set_at.astimezone(UTC)
        return day_start.astimezone(UTC)
