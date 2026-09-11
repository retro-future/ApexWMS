"""The quoted rate of the day — W9 B1.

The rate log is append-only for the same reason the two price logs are:
a sale points at the row it was struck against, so re-quoting a day cannot
move a figure a closed month already reported.

Nothing here converts anything. The rate is recorded beside the money, not
applied to it, and B7 is where a report starts using it.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from application.commands.set_exchange_rate import SetExchangeRateCommand
from application.queries.get_current_rates import GetCurrentRatesQuery
from application.queries.list_exchange_rates import ListExchangeRatesQuery
from domain.enums import AcquisitionSource, DeviceCondition, RateKind
from domain.errors import InvalidExchangeRateError
from domain.value_objects import Currency
from tests.application.builders import World, make_world

# The fake clock's noon UTC is 17:00 in Tashkent, so the store's own day is
# the first of July whichever way the timezone is read.
NOW = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def world() -> World:
    return make_world()


async def quote(world: World, som: str, kind: RateKind = RateKind.SALE, **rest):
    result = await world.set_exchange_rate().handle(
        SetExchangeRateCommand(kind=kind, som_per_usd=som, **rest)
    )
    assert result.data is not None
    return result.data


async def current(world: World):
    result = await world.get_current_rates().handle(GetCurrentRatesQuery())
    assert result.data is not None
    return result.data


class TestQuotingARate:
    async def test_it_is_recorded_for_the_stores_own_today(self, world):
        quoted = await quote(world, "12000")

        assert quoted.som_per_usd == "12000"
        assert quoted.effective_on == NOW.date()
        assert quoted.is_stale is False

    async def test_re_quoting_the_same_day_appends_rather_than_replaces(self, world):
        await quote(world, "12000")
        await quote(world, "12200")

        assert len(world.exchange_rates.rows) == 2
        rates = await current(world)
        assert rates.sale is not None
        assert rates.sale.som_per_usd == "12200"

    async def test_the_two_kinds_are_independent(self, world):
        await quote(world, "12000", RateKind.SALE)
        await quote(world, "11500", RateKind.BUYBACK)

        rates = await current(world)

        assert rates.sale is not None
        assert rates.buyback is not None
        assert rates.sale.som_per_usd == "12000"
        assert rates.buyback.som_per_usd == "11500"

    async def test_a_fractional_rate_survives_the_round_trip(self, world):
        quoted = await quote(world, "12345.5")

        assert quoted.som_per_usd == "12345.5"


class TestWhatIsNotARate:
    @pytest.mark.parametrize("bad", ["0", "-12000"])
    async def test_a_rate_that_is_not_positive_is_refused(self, world, bad):
        with pytest.raises(InvalidExchangeRateError):
            await quote(world, bad)

    async def test_a_rate_that_is_not_a_number_is_refused(self, world):
        with pytest.raises(InvalidExchangeRateError):
            await quote(world, "twelve thousand")

    async def test_more_precision_than_four_places_is_refused(self, world):
        with pytest.raises(InvalidExchangeRateError):
            await quote(world, "12000.123456")


class TestReadingTheRateInForce:
    async def test_a_store_that_has_never_quoted_one_reads_empty(self, world):
        rates = await current(world)

        assert rates.sale is None
        assert rates.buyback is None
        assert rates.today == NOW.date()

    async def test_yesterdays_rate_is_still_returned_and_marked_stale(self, world):
        """The counter is not blocked by a manager who overslept; it is
        told the figure is yesterday's."""
        await quote(world, "12000", effective_on=NOW.date() - timedelta(days=1))

        rates = await current(world)

        assert rates.sale is not None
        assert rates.sale.som_per_usd == "12000"
        assert rates.sale.is_stale is True

    async def test_todays_quote_wins_over_yesterdays(self, world):
        await quote(world, "12000", effective_on=NOW.date() - timedelta(days=1))
        await quote(world, "12400")

        rates = await current(world)

        assert rates.sale is not None
        assert rates.sale.som_per_usd == "12400"
        assert rates.sale.is_stale is False

    async def test_the_history_holds_every_quote_of_one_kind(self, world):
        await quote(world, "12000", RateKind.SALE)
        await quote(world, "12200", RateKind.SALE)
        await quote(world, "11500", RateKind.BUYBACK)

        listed = await world.list_exchange_rates().handle(
            ListExchangeRatesQuery(kind=RateKind.SALE)
        )

        assert listed.total_items == 2
        assert {row.som_per_usd for row in listed.data} == {"12000", "12200"}


class TestASaleRemembersTheRateItWasStruckAt:
    """The payoff of B1: the dollar price and the som taken are two facts,
    and the rate the store was quoting is the third that lets anyone
    compare them later."""

    async def test_confirming_stamps_the_rate_in_force(self, world):
        from tests.application.test_sales_invoice import (
            a_place,
            catalogued,
            confirm,
            in_stock,
            opened,
            scan,
        )

        await quote(world, "12000")
        location = a_place(world)
        product = catalogued(world, price="600")
        unit = await in_stock(world, product, location)
        invoice = await opened(world, location)
        await scan(world, invoice, str(unit.imei))

        await confirm(world, invoice)

        quoted = world.exchange_rates.rows[0]
        assert invoice.sale_rate_id == quoted.id

    async def test_a_store_with_no_rate_still_sells(self, world):
        """A shop that has not been shown the rate card yet is not stopped
        by it; the sale simply carries no rate."""
        from tests.application.test_sales_invoice import (
            a_place,
            catalogued,
            confirm,
            in_stock,
            opened,
            scan,
        )

        location = a_place(world)
        product = catalogued(world, price="600")
        unit = await in_stock(world, product, location)
        invoice = await opened(world, location)
        await scan(world, invoice, str(unit.imei))

        result = await confirm(world, invoice)

        assert result.success is True
        assert invoice.sale_rate_id is None


class TestATradeInRemembersWhatItBoughtDollarsAt:
    """The buying twin of the sale snapshot (W9 B2)."""

    async def test_confirming_stamps_the_buying_rate(self, world):
        from tests.application.test_goods_receipt import confirm, opened, scan

        await quote(world, "11500", kind=RateKind.BUYBACK)
        receipt, _, _ = await opened(world, source=AcquisitionSource.TRADE_IN)
        await scan(
            world,
            receipt,
            condition=DeviceCondition.USED,
            acquisition_cost="330",
            asking_price="420",
            cash_paid="3795000",
            cash_paid_currency=Currency.UZS,
        )

        await confirm(world, receipt)

        assert receipt.buyback_rate_id == world.exchange_rates.rows[0].id

    async def test_the_selling_rate_is_not_what_a_purchase_takes(self, world):
        from tests.application.test_goods_receipt import confirm, opened, scan

        await quote(world, "12500", kind=RateKind.SALE)
        receipt, _, _ = await opened(world, source=AcquisitionSource.TRADE_IN)
        await scan(
            world,
            receipt,
            condition=DeviceCondition.USED,
            acquisition_cost="330",
            asking_price="420",
            cash_paid="3795000",
            cash_paid_currency=Currency.UZS,
        )

        await confirm(world, receipt)

        assert receipt.buyback_rate_id is None

    async def test_a_supplier_receipt_takes_no_rate(self, world):
        from tests.application.test_goods_receipt import confirm, opened, scan

        await quote(world, "11500", kind=RateKind.BUYBACK)
        receipt, _, _ = await opened(world)
        await scan(world, receipt, acquisition_cost="700")

        await confirm(world, receipt)

        assert receipt.buyback_rate_id is None


class TestHowARateReads:
    """The column keeps four decimal places whether a rate uses them or
    not, and echoing that padding back reads like a different number."""

    async def test_a_whole_rate_carries_no_decimal_padding(self, world):
        stored = world.exchange_rates
        await quote(world, "12500")
        # What the database hands back, padded to the column's scale.
        stored.rows[-1].som_per_usd = Decimal("12500.0000")

        rates = await current(world)

        assert rates.sale is not None
        assert rates.sale.som_per_usd == "12500"

    async def test_a_real_decimal_survives(self, world):
        stored = world.exchange_rates
        await quote(world, "12345.5")
        stored.rows[-1].som_per_usd = Decimal("12345.5000")

        rates = await current(world)

        assert rates.sale is not None
        assert rates.sale.som_per_usd == "12345.5"
