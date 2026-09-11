"""One quoted rate, som per dollar, as of one business day (W9 B1).

Append-only like the two price logs: setting today's rate again is another
row, so a sale that pointed at the earlier one still reads the figure it was
struck at months later. Nothing in the domain converts with it; it is
recorded so a report can, and so the rate a sale was actually struck at can
be compared against the one the store quoted.

Decimal and never float, for the reason ``Money`` refuses floats: a rate is
multiplied by an amount, and a binary fraction here reintroduces exactly the
lost-cent problem the money model exists to prevent.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.enums import RateKind
from domain.errors import InvalidExchangeRateError

# Four is past what any store quotes and still far inside the column's
# scale, so rounding a rate is never this table's problem.
MAX_RATE_EXPONENT = 4


@dataclass(eq=False, kw_only=True)
class ExchangeRate(UuidEntity, TenantEntity):
    kind: RateKind
    # The business day the rate is quoted for, in the tenant's timezone.
    # Separate from ``set_at`` because a manager may enter yesterday's rate
    # this morning, and the day it applies to is what a report groups by.
    effective_on: date
    som_per_usd: Decimal
    user_id: UUID
    set_at: datetime

    def __post_init__(self) -> None:
        if isinstance(self.som_per_usd, float):
            raise InvalidExchangeRateError("a rate is a Decimal, never a float")
        if not isinstance(self.som_per_usd, Decimal):
            raise InvalidExchangeRateError(
                f"a rate must be a Decimal, got {type(self.som_per_usd).__name__}"
            )
        # Before the comparison below: NaN is not less than or equal to
        # anything, so it would pass a bare positivity check.
        if not self.som_per_usd.is_finite():
            raise InvalidExchangeRateError(
                f"{self.som_per_usd} is not a rate", rate=str(self.som_per_usd)
            )
        if self.som_per_usd <= 0:
            raise InvalidExchangeRateError(
                f"{self.som_per_usd} is not a rate — som per dollar is positive",
                rate=str(self.som_per_usd),
            )
        exponent = self.som_per_usd.as_tuple().exponent
        # Only a non-finite Decimal carries a string exponent, and those are
        # gone by here.
        assert isinstance(exponent, int)
        if -exponent > MAX_RATE_EXPONENT:
            raise InvalidExchangeRateError(
                f"{self.som_per_usd} has more than {MAX_RATE_EXPONENT} decimal places",
                rate=str(self.som_per_usd),
            )
