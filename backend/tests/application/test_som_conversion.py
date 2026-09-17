"""Which quoted rate a dollar figure is read at (W9 B3).

A store can move its rate two or three times a day, so the rate a figure is
read at is the one in force at its own moment, not the last one of its day.
Tashkent is UTC+5: 09:00Z is 14:00 local on the same date.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from application.services.som_conversion import SomConverter
from domain.entities import ExchangeRate
from domain.enums import RateKind
from domain.value_objects import Currency, Money

ZONE = "Asia/Tashkent"
MORNING = datetime(2026, 9, 15, 6, 7, tzinfo=UTC)
LATER_THAT_MORNING = datetime(2026, 9, 15, 6, 49, tzinfo=UTC)
BETWEEN_THEM = datetime(2026, 9, 15, 6, 12, tzinfo=UTC)


def a_quote(rate: str, set_at: datetime, effective_on: date | None = None) -> ExchangeRate:
    return ExchangeRate(
        kind=RateKind.SALE,
        effective_on=effective_on or (set_at + timedelta(hours=5)).date(),
        som_per_usd=Decimal(rate),
        user_id=uuid4(),
        set_at=set_at,
    )


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


class TestARateChangedDuringTheDay:
    def test_a_figure_between_two_quotes_takes_the_earlier_one(self):
        converter = SomConverter(
            [a_quote("12500", MORNING), a_quote("11850", LATER_THAT_MORNING)], ZONE
        )

        assert converter.on(BETWEEN_THEM) == Decimal("12500")
        assert converter.convert(usd("400"), BETWEEN_THEM) == Money(5_000_000, Currency.UZS)

    def test_a_figure_after_the_correction_takes_the_correction(self):
        converter = SomConverter(
            [a_quote("12500", MORNING), a_quote("11850", LATER_THAT_MORNING)], ZONE
        )

        assert converter.on(LATER_THAT_MORNING + timedelta(minutes=1)) == Decimal("11850")

    def test_a_quote_is_in_force_from_the_instant_it_was_set(self):
        converter = SomConverter(
            [a_quote("12500", MORNING), a_quote("11850", LATER_THAT_MORNING)], ZONE
        )

        assert converter.on(LATER_THAT_MORNING) == Decimal("11850")
        assert converter.on(LATER_THAT_MORNING - timedelta(microseconds=1)) == Decimal(
            "12500"
        )

    def test_before_the_days_first_quote_yesterdays_rate_still_holds(self):
        yesterday = MORNING - timedelta(days=1)
        converter = SomConverter(
            [a_quote("12400", yesterday), a_quote("12500", MORNING)], ZONE
        )

        assert converter.on(MORNING - timedelta(hours=1)) == Decimal("12400")

    def test_the_input_order_of_the_log_does_not_matter(self):
        converter = SomConverter(
            [a_quote("11850", LATER_THAT_MORNING), a_quote("12500", MORNING)], ZONE
        )

        assert converter.on(BETWEEN_THEM) == Decimal("12500")
        assert converter.rate_changes == [MORNING, LATER_THAT_MORNING]


class TestAQuoteForAnotherDay:
    def test_yesterdays_rate_entered_this_morning_counts_from_yesterdays_start(self):
        """The after-the-fact entry ``SetExchangeRateCommand`` allows: the
        figures of the day it names read at it, not only what came after."""
        yesterday = date(2026, 9, 14)
        converter = SomConverter(
            [a_quote("12300", MORNING, effective_on=yesterday)], ZONE
        )
        # 10:00 local on the 14th.
        yesterday_morning = datetime(2026, 9, 14, 5, 0, tzinfo=UTC)

        assert converter.on(yesterday_morning) == Decimal("12300")
        assert not converter.before_the_first_quote(yesterday_morning)

    def test_tomorrows_rate_set_in_advance_is_not_in_force_today(self):
        tomorrow = date(2026, 9, 16)
        converter = SomConverter(
            [a_quote("12500", MORNING), a_quote("13000", MORNING, effective_on=tomorrow)],
            ZONE,
        )
        # 00:00 local on the 16th.
        midnight = datetime(2026, 9, 15, 19, 0, tzinfo=UTC)

        assert converter.on(LATER_THAT_MORNING) == Decimal("12500")
        assert converter.on(midnight) == Decimal("13000")

    def test_two_entries_for_the_same_start_the_later_entry_wins(self):
        yesterday = date(2026, 9, 14)
        converter = SomConverter(
            [
                a_quote("12300", MORNING, effective_on=yesterday),
                a_quote("12350", LATER_THAT_MORNING, effective_on=yesterday),
            ],
            ZONE,
        )

        assert converter.on(datetime(2026, 9, 14, 5, 0, tzinfo=UTC)) == Decimal("12350")


class TestBeforeTheLog:
    def test_a_figure_before_every_quote_takes_the_earliest_rate(self):
        converter = SomConverter(
            [a_quote("12500", MORNING), a_quote("11850", LATER_THAT_MORNING)], ZONE
        )
        long_ago = datetime(2026, 1, 1, tzinfo=UTC)

        assert converter.on(long_ago) == Decimal("12500")
        assert converter.before_the_first_quote(long_ago)
        assert converter.before_the_first_quote(None)
        assert converter.on(None) == Decimal("12500")

    def test_an_empty_log_says_so(self):
        assert SomConverter([], ZONE).is_empty


class TestWhatIsConverted:
    def test_som_passes_through_untouched(self):
        converter = SomConverter([a_quote("12500", MORNING)], ZONE)

        assert converter.convert(Money(120_000, Currency.UZS), MORNING) == Money(
            120_000, Currency.UZS
        )

    def test_rounds_to_whole_som_half_up(self):
        converter = SomConverter([a_quote("12550", MORNING)], ZONE)

        # $0.01 at 12 550 is 125.5 som.
        assert converter.convert(Money(1, Currency.USD), MORNING) == Money(126, Currency.UZS)
