"""Units sold, revenue, returns, cost of goods and margin — FR-9.3, PRD §5.9.

Every figure keeps §4.6's sign, which describes cash: revenue is positive
because money came in, and ``cost_of_goods`` is **negative** because the
goods left. That is why ``margin`` is a plain sum of the two with no sign
flipped anywhere — the arithmetic that hides a sign is the one that gets it
wrong (see ``INVENTORY_SIGN`` in ``services/cost_pools.py`` for the same
trap in the other direction).

``returns`` is negative for the same reason: money went back out. It is a
figure of its own rather than a deduction from ``revenue`` because a store
wants to see both — how much was sold, and how much of it came back (§5.10).

Cancellations need no special handling: a reversal negates its original
(§4.3 rule 3), so a cancelled sale contributes nothing to any of the four.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.enums import TransactionType
from domain.value_objects import Currency, CurrencyTotals, Money


@dataclass(frozen=True, slots=True)
class SalesTotalsRow:
    """One ``(location, category, currency)`` subtotal, straight from SQL."""

    location_id: UUID | None
    location_name: str | None
    txn_type: TransactionType
    amount: Money


@dataclass(frozen=True, slots=True)
class SalesFigures:
    """The three per-currency figures, for one location or for the store."""

    units_sold: int = 0
    revenue: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
    cost_of_goods: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
    returns: CurrencyTotals = field(default_factory=CurrencyTotals.empty)

    @property
    def margin(self) -> dict[Currency, Money]:
        """Revenue plus returns plus cost, per currency and never across them.

        Both the cost and the refunds are already negative, so this is
        addition throughout. A currency present on only one side still gets a
        figure — a sale with no COGS behind it is a margin worth seeing, not
        a row to drop.
        """
        return {
            currency: (
                self.revenue.of(currency)
                + self.returns.of(currency)
                + self.cost_of_goods.of(currency)
            )
            for currency in (
                self.revenue.currencies
                | self.cost_of_goods.currencies
                | self.returns.currencies
            )
        }


@dataclass(frozen=True, slots=True)
class LocationSales:
    location_id: UUID | None
    location_name: str | None
    figures: SalesFigures


@dataclass(frozen=True, slots=True)
class SalesSummary:
    from_date: datetime | None
    to_date: datetime | None
    locations: list[LocationSales]
    total: SalesFigures
