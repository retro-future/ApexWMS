"""Money round-trip tests for both currencies — required at M0 (PRD §11:
the 100x exponent-corruption bug is mitigated before any money is persisted).
"""

from decimal import Decimal

import pytest

from apexwms.domain.errors import CurrencyMismatchError, InvalidMoneyError
from apexwms.domain.value_objects import Currency, Money


class TestExponents:
    def test_uzs_has_exponent_zero(self):
        assert Currency.UZS.exponent == 0

    def test_usd_has_exponent_two(self):
        assert Currency.USD.exponent == 2

    def test_fr_2_9_uzs_1000_renders_as_thousand_som(self):
        assert Money(1000, Currency.UZS).format() == "1 000 so'm"

    def test_fr_2_9_usd_1000_renders_as_ten_dollars(self):
        assert Money(1000, Currency.USD).format() == "$10.00"

    def test_usd_round_trip_major_minor(self):
        m = Money.from_major("1000", Currency.USD)
        assert m.amount_minor == 100_000
        assert m.as_major() == Decimal("1000")

    def test_uzs_round_trip_major_minor(self):
        m = Money.from_major("1000", Currency.UZS)
        assert m.amount_minor == 1000
        assert m.as_major() == Decimal("1000")

    def test_usd_keeps_cents_exactly(self):
        m = Money.from_major("10.57", Currency.USD)
        assert m.amount_minor == 1057
        assert m.format() == "$10.57"

    def test_uzs_rejects_fractional_som(self):
        with pytest.raises(InvalidMoneyError):
            Money.from_major("100.50", Currency.UZS)

    def test_usd_rejects_fractional_cents(self):
        with pytest.raises(InvalidMoneyError):
            Money.from_major("10.505", Currency.USD)

    def test_big_uzs_amounts_survive(self):
        # Annual turnover runs into the trillions of som (PRD §4.5).
        m = Money(12_000_000_000_000, Currency.UZS)
        assert m.format() == "12 000 000 000 000 so'm"


class TestConstruction:
    def test_float_is_not_money(self):
        with pytest.raises(InvalidMoneyError):
            Money(10.5, Currency.USD)  # type: ignore[arg-type]

    def test_float_major_is_rejected(self):
        with pytest.raises(InvalidMoneyError):
            Money.from_major(10.5, Currency.USD)  # type: ignore[arg-type]

    def test_bool_is_not_money(self):
        with pytest.raises(InvalidMoneyError):
            Money(True, Currency.UZS)  # type: ignore[arg-type]

    def test_bare_string_currency_is_rejected(self):
        with pytest.raises(InvalidMoneyError):
            Money(1000, "UZS")  # type: ignore[arg-type]

    def test_negative_amounts_are_allowed(self):
        # Compensating / reversing entries are negative by design.
        m = Money(-500, Currency.USD)
        assert m.is_negative
        assert m.format() == "-$5.00"


class TestArithmetic:
    def test_add_same_currency(self):
        assert Money(100, Currency.UZS) + Money(200, Currency.UZS) == Money(300, Currency.UZS)

    def test_subtract_same_currency(self):
        assert Money(300, Currency.USD) - Money(100, Currency.USD) == Money(200, Currency.USD)

    def test_fr_2_10_add_across_currencies_raises(self):
        with pytest.raises(CurrencyMismatchError):
            Money(100, Currency.UZS) + Money(100, Currency.USD)

    def test_fr_2_10_compare_across_currencies_raises(self):
        with pytest.raises(CurrencyMismatchError):
            Money(100, Currency.UZS) < Money(100, Currency.USD)  # noqa: B015

    def test_add_bare_int_raises(self):
        with pytest.raises(CurrencyMismatchError):
            Money(100, Currency.UZS) + 100  # type: ignore[operator]

    def test_multiply_by_int(self):
        assert Money(1057, Currency.USD) * 3 == Money(3171, Currency.USD)
        assert 3 * Money(1057, Currency.USD) == Money(3171, Currency.USD)

    def test_multiply_by_float_raises(self):
        with pytest.raises(InvalidMoneyError):
            Money(100, Currency.USD) * 1.5  # type: ignore[operator]

    def test_negation(self):
        assert -Money(100, Currency.UZS) == Money(-100, Currency.UZS)

    def test_equality_is_value_based(self):
        assert Money(100, Currency.UZS) == Money(100, Currency.UZS)
        assert Money(100, Currency.UZS) != Money(100, Currency.USD)

    def test_ordering_same_currency(self):
        assert Money(100, Currency.UZS) < Money(200, Currency.UZS)
        assert Money(200, Currency.UZS) >= Money(200, Currency.UZS)
