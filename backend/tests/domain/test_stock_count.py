"""``StockCount`` and its two kinds of row — PRD §5.6, FR-6.1 to FR-6.4b.

Every rule here is a pure function of the count's own rows. What an
adjustment is *worth* is not — that needs the live unit and a replayed cost
pool — so it lives in ``CountPoster`` and is tested against the application
harness instead. Nothing below imports a repository or awaits anything.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from domain.entities import StockCount, StockCountLine, StockCountUnit
from domain.enums import CountOutcome, DocumentStatus
from domain.errors import (
    CountAlreadyClosedError,
    CountNotClosedError,
    DocumentNotDraftError,
    EmptyDocumentError,
    InvalidLineError,
    InvalidMoneyError,
    UnpricedUnitError,
)
from domain.value_objects import IMEI, Currency, Money

NOW = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=2)

PHONE_IMEI = "490154203237518"
OTHER_IMEI = "356938035643809"
THIRD_IMEI = "358240051111110"


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def counted_unit(
    count_id: UUID | None = None, *, imei: str = PHONE_IMEI, **overrides: object
) -> StockCountUnit:
    fields: dict[str, object] = {
        "id": uuid4(),
        "stock_count_id": count_id or uuid4(),
        "imei": IMEI.parse(imei),
        "device_unit_id": uuid4(),
        "product_id": uuid4(),
        "expected": True,
        "scanned": True,
    }
    fields.update(overrides)
    return StockCountUnit(**fields)  # type: ignore[arg-type]


def surprise(
    count_id: UUID | None = None, *, imei: str = OTHER_IMEI, **overrides: object
) -> StockCountUnit:
    """A scan of an IMEI the store has no row for (FR-6.4b)."""
    fields: dict[str, object] = {
        "device_unit_id": None,
        "product_id": None,
        "expected": False,
        "scanned": True,
    }
    fields.update(overrides)
    return counted_unit(count_id, imei=imei, **fields)


def accessory_line(
    count_id: UUID | None = None, *, expected: int = 10, counted: int | None = None
) -> StockCountLine:
    return StockCountLine(
        id=uuid4(),
        stock_count_id=count_id or uuid4(),
        product_id=uuid4(),
        expected_quantity=expected,
        counted_quantity=counted,
    )


def a_count(
    *units: StockCountUnit,
    lines: list[StockCountLine] | None = None,
    status: DocumentStatus = DocumentStatus.DRAFT,
    closed_at: datetime | None = None,
) -> StockCount:
    return StockCount(
        id=uuid4(),
        number="SC-2026-0001",
        status=status,
        location_id=uuid4(),
        created_by=uuid4(),
        created_at=NOW,
        closed_at=closed_at,
        closed_by=uuid4() if closed_at is not None else None,
        units=list(units),
        lines=lines or [],
    )


class TestARowKnowsWhichListItIsOn:
    """FR-6.3: matched, missing and unexpected are derived, never stored."""

    def test_expected_and_scanned_is_matched(self):
        assert counted_unit().outcome is CountOutcome.MATCHED

    def test_expected_and_not_scanned_is_missing(self):
        assert counted_unit(scanned=False).outcome is CountOutcome.MISSING

    def test_scanned_but_not_expected_is_unexpected(self):
        assert counted_unit(expected=False).outcome is CountOutcome.UNEXPECTED

    def test_a_row_that_is_neither_has_no_reason_to_exist(self):
        with pytest.raises(InvalidLineError):
            counted_unit(expected=False, scanned=False)

    def test_an_expected_row_names_the_handset_the_books_hold(self):
        with pytest.raises(InvalidLineError):
            counted_unit(device_unit_id=None)

    def test_only_a_row_with_no_handset_behind_it_is_a_surprise(self):
        assert surprise().is_surprise is True
        # Known to the store, just not expected here — it already has a cost.
        assert counted_unit(expected=False).is_surprise is False

    def test_the_three_lists_come_back_separately(self):
        count = a_count(
            counted_unit(imei=PHONE_IMEI),
            counted_unit(imei=OTHER_IMEI, scanned=False),
            surprise(imei=THIRD_IMEI),
        )
        assert [str(u.imei) for u in count.matched()] == [PHONE_IMEI]
        assert [str(u.imei) for u in count.missing()] == [OTHER_IMEI]
        assert [str(u.imei) for u in count.unexpected()] == [THIRD_IMEI]


class TestACostNeedsSomethingToBeDenominatedIn:
    """§4.5 rule 3: an amount belongs to the catalog row it names."""

    def test_a_cost_without_a_product_is_refused(self):
        with pytest.raises(InvalidLineError):
            surprise(acquisition_cost=usd("300"))

    def test_a_cost_with_a_product_is_fine(self):
        row = surprise(product_id=uuid4(), acquisition_cost=usd("300"))
        assert row.acquisition_cost == usd("300")

    def test_a_negative_cost_is_refused(self):
        with pytest.raises(InvalidMoneyError):
            surprise(product_id=uuid4(), acquisition_cost=Money(-1, Currency.USD))


class TestAnAccessoryLineDistinguishesZeroFromUncounted:
    """FR-6.2: a shelf nobody looked at is not a shelf found empty."""

    def test_uncounted_adjusts_nothing(self):
        assert accessory_line(expected=10, counted=None).delta == 0

    def test_counted_zero_is_a_total_loss(self):
        assert accessory_line(expected=10, counted=0).delta == -10

    def test_a_surplus_is_positive(self):
        assert accessory_line(expected=10, counted=12).delta == 2

    def test_a_negative_count_is_not_a_number_of_things(self):
        with pytest.raises(InvalidLineError):
            accessory_line(expected=10, counted=-1)


class TestClosingFreezesTheReport:
    """FR-6.3: what is reported and what is applied describe one shelf."""

    def test_closing_stamps_who_and_when(self):
        count = a_count(counted_unit())
        actor = uuid4()

        count.close(LATER, actor)

        assert count.is_closed
        assert count.closed_at == LATER
        assert count.closed_by == actor

    def test_a_closed_count_takes_no_more_scans(self):
        count = a_count(counted_unit())
        count.close(LATER, uuid4())

        with pytest.raises(CountAlreadyClosedError):
            count.assert_countable()

    def test_a_closed_count_still_takes_a_surprises_valuation(self):
        """Pricing a known surprise is not a new finding (FR-6.4b)."""
        count = a_count(surprise())
        count.close(LATER, uuid4())

        count.assert_valuable()

    def test_a_confirmed_counts_valuation_is_closed_too(self):
        count = a_count(surprise(), status=DocumentStatus.CONFIRMED, closed_at=LATER)

        with pytest.raises(DocumentNotDraftError):
            count.assert_valuable()

    def test_closing_a_count_of_nothing_is_refused(self):
        with pytest.raises(EmptyDocumentError):
            a_count().close(LATER, uuid4())

    def test_a_confirmed_count_cannot_be_closed_again(self):
        count = a_count(counted_unit(), status=DocumentStatus.CONFIRMED)

        with pytest.raises(DocumentNotDraftError):
            count.close(LATER, uuid4())

    def test_closing_writes_no_status_change(self):
        """A closed count is still a draft: it has found discrepancies and
        applied none of them, which is the state a Manager reviews."""
        count = a_count(counted_unit())
        count.close(LATER, uuid4())

        assert count.status is DocumentStatus.DRAFT


class TestConfirmingLetsRealityWin:
    def test_a_count_that_was_never_closed_is_refused(self):
        count = a_count(counted_unit())

        with pytest.raises(CountNotClosedError):
            count.confirm(LATER, uuid4())

    def test_a_closed_count_confirms(self):
        count = a_count(counted_unit(), closed_at=LATER)
        actor = uuid4()

        count.confirm(LATER, actor)

        assert count.status is DocumentStatus.CONFIRMED
        assert count.confirmed_by == actor

    def test_a_confirmed_count_cannot_confirm_twice(self):
        count = a_count(counted_unit(), closed_at=LATER)
        count.confirm(LATER, uuid4())

        with pytest.raises(DocumentNotDraftError):
            count.confirm(LATER, uuid4())


class TestASurpriseMustBeIdentifiedAndCosted:
    """FR-6.4b: a surplus is booked at its value, so it needs one."""

    def test_a_surprise_naming_no_product_blocks_the_confirm(self):
        count = a_count(surprise(), closed_at=LATER)

        with pytest.raises(UnpricedUnitError, match=OTHER_IMEI):
            count.confirm(LATER, uuid4())

    def test_a_surprise_with_a_product_but_no_cost_blocks_the_confirm(self):
        count = a_count(surprise(product_id=uuid4()), closed_at=LATER)

        with pytest.raises(UnpricedUnitError, match="what these cost"):
            count.confirm(LATER, uuid4())

    def test_every_offending_imei_is_named_in_one_message(self):
        """The person fixing this is standing at a shelf, and one error at a
        time turns that into ten round trips."""
        count = a_count(
            surprise(imei=OTHER_IMEI, product_id=uuid4()),
            surprise(imei=THIRD_IMEI, product_id=uuid4()),
            closed_at=LATER,
        )

        with pytest.raises(UnpricedUnitError) as raised:
            count.confirm(LATER, uuid4())

        assert OTHER_IMEI in str(raised.value)
        assert THIRD_IMEI in str(raised.value)

    def test_a_costed_surprise_confirms(self):
        count = a_count(
            surprise(product_id=uuid4(), acquisition_cost=usd("300")), closed_at=LATER
        )

        count.confirm(LATER, uuid4())

        assert count.status is DocumentStatus.CONFIRMED

    def test_an_unexpected_handset_the_store_knows_needs_no_cost(self):
        """It already carries one: the store bought it, and finding it in the
        wrong place has not changed what it paid."""
        count = a_count(counted_unit(expected=False), closed_at=LATER)

        count.confirm(LATER, uuid4())

        assert count.status is DocumentStatus.CONFIRMED

    def test_a_missing_handset_needs_no_cost_either(self):
        count = a_count(counted_unit(scanned=False), closed_at=LATER)

        count.confirm(LATER, uuid4())

        assert count.status is DocumentStatus.CONFIRMED


class TestLookups:
    def test_a_scan_finds_the_row_the_snapshot_already_wrote(self):
        row = counted_unit(scanned=False)
        count = a_count(row)

        assert count.unit_for_imei(IMEI.parse(PHONE_IMEI)) is row

    def test_an_imei_the_count_never_saw_is_none(self):
        count = a_count(counted_unit())

        assert count.unit_for_imei(IMEI.parse(OTHER_IMEI)) is None

    def test_a_line_is_found_by_its_product(self):
        line = accessory_line()
        count = a_count(counted_unit(), lines=[line])

        assert count.line_for_product(line.product_id) is line
