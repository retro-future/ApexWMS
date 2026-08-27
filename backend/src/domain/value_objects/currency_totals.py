"""Running totals, one per currency, that cannot merge two — PRD §4.5 rule 4.

The key is always read off the amount and never passed in, which is what
makes "accidentally summing across currencies" — the highest-risk mistake
in §11's table — structurally impossible rather than merely tested for. A
report that holds one of these has nowhere to write a combined figure.

Immutable like every other value object here: ``add`` returns a new
instance, the way ``CostPool.receive`` does. The volumes are report groups
and ledger categories, not rows.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from domain.value_objects.currency import Currency
from domain.value_objects.money import Money


@dataclass(frozen=True, slots=True)
class CurrencyTotals:
    amounts: Mapping[Currency, Money] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "amounts", MappingProxyType(dict(self.amounts)))

    @classmethod
    def empty(cls) -> CurrencyTotals:
        return cls()

    def add(self, amount: Money) -> CurrencyTotals:
        running = self.amounts.get(amount.currency)
        return CurrencyTotals(
            {
                **self.amounts,
                amount.currency: amount if running is None else running + amount,
            }
        )

    def merge(self, other: CurrencyTotals) -> CurrencyTotals:
        totals = self
        for amount in other.amounts.values():
            totals = totals.add(amount)
        return totals

    def of(self, currency: Currency) -> Money:
        """The running total in *currency*, or zero in it — never a total
        borrowed from another column."""
        return self.amounts.get(currency, Money.zero(currency))

    def as_dict(self) -> dict[Currency, Money]:
        return dict(self.amounts)

    @property
    def currencies(self) -> frozenset[Currency]:
        return frozenset(self.amounts)

    @property
    def is_empty(self) -> bool:
        return not self.amounts
