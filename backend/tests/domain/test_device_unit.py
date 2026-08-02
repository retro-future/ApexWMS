"""``DeviceUnit`` invariants — PRD §4.2, §4.5b, FR-2.16.

A handset that cannot exist in an invalid state deletes a class of bugs
before any repository sees it. The two worth reading are the currency pair
(a unit cannot be denominated differently from its catalog row) and
``cash_paid`` (a fact about the deal that must never join a sum).
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.entities import DeviceUnit
from domain.enums import DeviceCondition, DeviceStatus
from domain.errors import (
    CurrencyMismatchError,
    InvalidDeviceUnitError,
    InvalidMoneyError,
    UnitNotRepriceableError,
)
from domain.value_objects import IMEI, Currency, Money

NOW = datetime(2026, 3, 1, tzinfo=UTC)
IMEI_A = "490154203237518"


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def unit(**overrides) -> DeviceUnit:
    fields = {
        "imei": IMEI(IMEI_A),
        "product_id": uuid4(),
        "status": DeviceStatus.IN_STOCK,
        "location_id": uuid4(),
        "acquisition_cost": usd("380"),
        "condition": DeviceCondition.NEW,
        "created_at": NOW,
    }
    return DeviceUnit(**{**fields, **overrides})


class TestIdentity:
    def test_two_handsets_with_the_same_attributes_are_not_equal(self):
        """PRD §7.6's teaching case: identity is not attributes. Two
        sealed iPhones off the same pallet are different phones."""
        shared = {"product_id": uuid4(), "location_id": uuid4()}

        assert unit(**shared) != unit(**shared)

    def test_a_unit_equals_itself_across_a_reload(self):
        original = unit()

        reloaded = unit(id=original.id, product_id=original.product_id)

        assert reloaded == original


class TestMoneyOnAUnit:
    def test_the_asking_price_must_share_the_units_currency(self):
        """FR-2.13: there is no per-unit currency, and a price in any other
        is rejected (§4.5 rule 3)."""
        with pytest.raises(CurrencyMismatchError):
            unit(asking_price=Money.from_major("5000000", Currency.UZS))

    def test_the_currency_a_unit_reports_is_the_one_it_was_bought_in(self):
        assert unit().currency is Currency.USD

    def test_neither_cost_nor_price_may_be_negative(self):
        with pytest.raises(InvalidMoneyError):
            unit(acquisition_cost=usd("-1"))
        with pytest.raises(InvalidMoneyError):
            unit(asking_price=usd("-1"))

    def test_a_free_handset_costs_zero_rather_than_being_refused(self):
        """Zero is a real acquisition cost — a promotional unit, a
        warranty replacement. Only negative is impossible."""
        assert unit(acquisition_cost=usd("0")).acquisition_cost.is_zero


class TestCashPaidIsAFactAndNotAnAmount:
    """§4.5b: a trade-in bought for som against a USD catalog row. The som
    figure is recorded beside the booked cost and enters no ledger, no
    total, and no report — which is why it is a bare pair and not a
    ``Money`` that arithmetic would happily accept."""

    def test_a_som_paid_trade_in_books_dollars_and_records_som(self):
        traded = unit(
            condition=DeviceCondition.USED,
            acquisition_cost=usd("330"),
            asking_price=usd("420"),
            cash_paid_minor=4_200_000,
            cash_paid_currency=Currency.UZS,
        )

        assert traded.acquisition_cost == usd("330")
        assert traded.cash_paid_display() == "4 200 000 so'm"

    def test_the_pair_is_both_or_neither(self):
        with pytest.raises(InvalidMoneyError):
            unit(cash_paid_minor=4_200_000)
        with pytest.raises(InvalidMoneyError):
            unit(cash_paid_currency=Currency.UZS)

    def test_a_unit_that_paid_what_it_booked_shows_no_cash_figure(self):
        assert unit().cash_paid_display() is None

    def test_the_som_figure_is_a_string_and_never_a_money(self):
        """The type is the guard: ``Money`` would join a ``sum()``, and
        FR-3.4d's whole point is that this figure cannot."""
        traded = unit(cash_paid_minor=4_200_000, cash_paid_currency=Currency.UZS)

        assert isinstance(traded.cash_paid_display(), str)
        assert not isinstance(traded.cash_paid_minor, Money)


class TestAUnitIsSomewhereOrItIsGone:
    @pytest.mark.parametrize("status", [DeviceStatus.IN_STOCK, DeviceStatus.RESERVED])
    def test_stock_on_hand_must_have_a_location(self, status):
        with pytest.raises(InvalidDeviceUnitError):
            unit(status=status, location_id=None)

    @pytest.mark.parametrize(
        "status",
        [DeviceStatus.SOLD, DeviceStatus.RETURNED_TO_SUPPLIER, DeviceStatus.WRITTEN_OFF],
    )
    def test_a_unit_that_has_left_holds_no_location(self, status):
        with pytest.raises(InvalidDeviceUnitError):
            unit(status=status)

        assert unit(status=status, location_id=None).location_id is None


class TestRepricingIsOnlyForStockOnTheShelf:
    @pytest.mark.parametrize("status", [DeviceStatus.IN_STOCK, DeviceStatus.RESERVED])
    def test_stock_on_hand_may_be_repriced(self, status):
        """FR-2.16 allows RESERVED on purpose: an open draft holding the
        unit simply picks the new price up at confirm (FR-4.5b1)."""
        unit(status=status).assert_repriceable()

    @pytest.mark.parametrize(
        "status",
        [DeviceStatus.SOLD, DeviceStatus.RETURNED_TO_SUPPLIER, DeviceStatus.WRITTEN_OFF],
    )
    def test_a_unit_that_has_left_cannot_be_repriced(self, status):
        gone = unit(status=status, location_id=None)

        with pytest.raises(UnitNotRepriceableError) as raised:
            gone.assert_repriceable()

        # FR-2.16: the error states the unit's status, so the operator
        # learns why rather than that it merely failed.
        assert status.value in str(raised.value)
