"""Weighted-average cost for quantity products — PRD §4.6.

The load-bearing property is
``test_selling_a_pool_out_completely_leaves_nothing_behind``: a pool that
has been fully issued must be worth exactly zero. Anything else and
FR-10.7's reconciliation fails by an amount nobody can explain, months
after the rounding that caused it.
"""

import pytest

from domain.errors import CurrencyMismatchError, InvalidMovementError
from domain.value_objects import CostPool, Currency, Money


def som(major: str | int) -> Money:
    return Money.from_major(major, Currency.UZS)


class TestReceiving:
    def test_an_empty_pool_is_worth_nothing_and_has_no_average(self):
        pool = CostPool.empty(Currency.UZS)

        assert pool.quantity == 0
        assert pool.value == som(0)
        assert pool.average_unit_cost is None

    def test_receiving_sets_the_average_to_what_was_paid(self):
        pool = CostPool.empty(Currency.UZS).receive(10, som(30_000))

        assert pool.quantity == 10
        assert pool.value == som(300_000)
        assert pool.average_unit_cost == som(30_000)

    def test_a_second_purchase_at_a_different_price_moves_the_average(self):
        """The whole point of weighted average: when accessory prices move,
        the average moves with them."""
        pool = CostPool.empty(Currency.UZS).receive(10, som(30_000)).receive(10, som(40_000))

        assert pool.quantity == 20
        assert pool.average_unit_cost == som(35_000)

    def test_a_pool_cannot_be_fed_another_currency(self):
        """An accessory's pool is denominated by its product, and nothing
        in this system converts (§4.5 rule 1)."""
        pool = CostPool.empty(Currency.UZS).receive(10, som(30_000))

        with pytest.raises(CurrencyMismatchError):
            pool.receive(1, Money.from_major("25", Currency.USD))

    def test_receiving_nothing_is_refused(self):
        with pytest.raises(InvalidMovementError):
            CostPool.empty(Currency.UZS).receive(0, som(30_000))


class TestIssuing:
    def test_cogs_is_the_average_when_the_pool_is_uniform(self):
        pool = CostPool.empty(Currency.UZS).receive(10, som(30_000))

        remaining, cogs = pool.issue(3)

        assert cogs == som(90_000)
        assert remaining.quantity == 7
        assert remaining.value == som(210_000)

    def test_cogs_uses_the_average_at_the_time_of_sale(self):
        """Not the price of the batch the unit physically came from — a box
        of cases has no per-unit identity to trace back (§4.1)."""
        pool = CostPool.empty(Currency.UZS).receive(10, som(30_000)).receive(10, som(40_000))

        _, cogs = pool.issue(1)

        assert cogs == som(35_000)

    def test_selling_a_pool_out_completely_leaves_nothing_behind(self):
        """The property FR-10.7 rests on. An average of 33 333.33 so'm
        rounds, and "average × quantity" would strand the residue as stock
        value for goods that are gone."""
        pool = CostPool.empty(Currency.UZS).receive(3, som(100_001))

        remaining, _ = pool.issue(3)

        assert remaining.quantity == 0
        assert remaining.value == som(0)

    def test_issuing_one_at_a_time_drains_the_pool_exactly(self):
        """The same property under the worst case for rounding: three
        separate sales out of a pool that does not divide evenly."""
        pool = CostPool.empty(Currency.UZS).receive(3, som(100_001))

        total = som(0)
        for _ in range(3):
            pool, cogs = pool.issue(1)
            total = total + cogs

        assert pool.quantity == 0
        assert pool.value == som(0)
        assert total == som(300_003)

    def test_cogs_never_exceeds_what_the_pool_holds(self):
        pool = CostPool.empty(Currency.UZS).receive(7, som(12_345))

        remaining, cogs = pool.issue(7)

        assert cogs == pool.value
        assert remaining.value == som(0)

    def test_issuing_more_than_is_held_is_refused(self):
        """FR-4.7: a confirm that would oversell is rejected atomically —
        never partly fulfilled, never booked as negative stock."""
        pool = CostPool.empty(Currency.UZS).receive(2, som(30_000))

        with pytest.raises(InvalidMovementError):
            pool.issue(3)

    def test_issuing_nothing_is_refused(self):
        pool = CostPool.empty(Currency.UZS).receive(2, som(30_000))

        with pytest.raises(InvalidMovementError):
            pool.issue(0)


class TestAPoolCannotDescribeAnImpossibleStore:
    def test_a_negative_quantity_is_refused(self):
        with pytest.raises(InvalidMovementError):
            CostPool(quantity=-1, value=som(0))

    def test_value_cannot_outlive_the_goods(self):
        """The exact condition the proportional-share rule exists to
        prevent, asserted directly."""
        with pytest.raises(InvalidMovementError):
            CostPool(quantity=0, value=som(5))


class TestUsdPoolsRoundOnCents:
    def test_a_dollar_pool_averages_in_cents(self):
        """USD has exponent 2, UZS has 0 — the arithmetic is the same, the
        unit is not, and no call site may assume either (§4.5)."""
        pool = CostPool.empty(Currency.USD).receive(3, Money.from_major("10.00", Currency.USD))

        assert pool.average_unit_cost == Money.from_major("10.00", Currency.USD)
        assert pool.value.amount_minor == 3000
