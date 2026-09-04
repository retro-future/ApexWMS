"""How stock is costed — PRD §4.6.

Two rules, because the two tracking types genuinely differ:

- **Serialized phones → specific identification.** Every ``DeviceUnit``
  carries its own ``acquisition_cost``; when that exact unit sells, its
  COGS is its own cost. Exact, no estimation. This is the payoff of
  serializing — valuation is not a model, it is a fact — and it needs no
  code beyond reading the field.
- **Quantity accessories → weighted average.** A box of cases has no
  per-unit identity, so the cost of one is whatever the pool of them
  averages out to. That pool is what this module maintains.

## Why an issue takes a *share* of the pool, not "average × quantity"

The obvious implementation computes an average unit cost, rounds it, and
multiplies. It is wrong in a way that only shows up months later: the
rounding residue stays behind, so a pool that has been fully sold out
still reports a few som of stock value, and FR-10.7's reconciliation —
closing inventory value against independently-computed on-hand value —
fails by an amount nobody can explain.

Taking a proportional share instead (``value × qty / quantity``, rounded
once) makes the last issue drain the pool **exactly**: when ``qty ==
quantity`` the share is the whole remaining value by construction. On-hand
value is then always precisely purchases − COGS − write-offs ± adjustments,
and the reconciliation is exact rather than approximately right.

This is also why COGS and the reconciliation both come through here rather
than each doing its own arithmetic: two roundings of the same figure in
two places is exactly how the two ledgers drift apart.
"""

from dataclasses import dataclass

from domain.errors import InvalidMovementError
from domain.value_objects.currency import Currency
from domain.value_objects.money import Money, round_half_up


@dataclass(frozen=True, slots=True)
class CostPool:
    """What a store holds of one quantity product, and what it is worth.

    Immutable: ``receive`` and ``issue`` return the next pool rather than
    mutating this one, so replaying a ledger is a fold and a caller cannot
    accidentally apply the same movement twice.
    """

    quantity: int
    value: Money

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise InvalidMovementError(
                f"a cost pool of {self.quantity} units — a location cannot hold "
                "less than nothing"
            )
        if self.quantity == 0 and not self.value.is_zero:
            raise InvalidMovementError(
                f"an empty pool worth {self.value.format()} — value cannot outlive "
                "the goods it belongs to"
            )

    @classmethod
    def empty(cls, currency: Currency) -> CostPool:
        return cls(quantity=0, value=Money.zero(currency))

    @property
    def average_unit_cost(self) -> Money | None:
        """What one unit is currently reckoned to have cost.

        ``None`` for an empty pool: nothing is held, so nothing has a cost.
        For *display and reporting only* — COGS comes from ``issue``, which
        does not round twice.
        """
        if self.quantity == 0:
            return None
        return Money(
            round_half_up(self.value.amount_minor, self.quantity), self.value.currency
        )

    def receive(self, quantity: int, unit_cost: Money) -> CostPool:
        """Add *quantity* units bought at *unit_cost* each.

        Cross-currency raises through ``Money`` — an accessory's pool is
        denominated by its product and nothing converts (§4.5 rule 1).
        """
        return self.receive_total(quantity, unit_cost * quantity)

    def receive_total(self, quantity: int, total_cost: Money) -> CostPool:
        """Add *quantity* units that cost *total_cost* altogether.

        The form the ledger actually speaks in: a ``PURCHASE`` entry
        records what a receipt line cost as one figure, and dividing it
        back out to a per-unit price only to multiply it up again would
        introduce a rounding error that was never in the data.
        """
        if quantity <= 0:
            raise InvalidMovementError(f"a receipt of {quantity} units receives nothing")
        if total_cost.is_negative:
            raise InvalidMovementError(
                f"a receipt worth {total_cost.format()} — goods coming in cannot "
                "reduce what the shelf is worth"
            )
        return CostPool(
            quantity=self.quantity + quantity,
            value=self.value + total_cost,
        )

    def issue(self, quantity: int) -> tuple[CostPool, Money]:
        """Take *quantity* units out; return the remaining pool and their cost.

        The cost is this issue's proportional share of the pool, rounded
        once — see the module docstring for why that, and not "average ×
        quantity".
        """
        if quantity <= 0:
            raise InvalidMovementError(f"an issue of {quantity} units issues nothing")
        if quantity > self.quantity:
            raise InvalidMovementError(
                f"cannot issue {quantity} units from a pool of {self.quantity} "
                "(FR-4.7: no partial fulfilment)"
            )
        cost = self.value.share(quantity, self.quantity)
        return CostPool(quantity=self.quantity - quantity, value=self.value - cost), cost
