"""``CustomerReturn`` — PRD §5.4b, FR-4.9 to FR-4.9g.

Only what is a pure function of the return's own lines: the refund ceiling,
the approval a reduction needs, the quantity a line may not exceed, and the
som rule on debt relief.

Whether the handset is *still sold*, whether this sale already had a return
against it, and whether the relief fits the outstanding balance all need
live rows, so they live in the poster and the confirm handler and are tested
against the application harness instead. Nothing below imports a repository
or awaits anything.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from domain.entities import CustomerReturn, CustomerReturnLine
from domain.enums import CustomerReturnReason, DocumentStatus, TrackingType
from domain.errors import (
    CurrencyMismatchError,
    DebtReliefError,
    DocumentNotDraftError,
    DuplicateScanError,
    EmptyDocumentError,
    InvalidLineError,
    InvalidMoneyError,
    RefundExceedsChargeError,
    UnapprovedRefundError,
)
from domain.value_objects import Currency, Money

NOW = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
USER = uuid4()


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def uzs(major: str) -> Money:
    return Money.from_major(major, Currency.UZS)


def a_line(document_id: UUID | None = None, **overrides: object) -> CustomerReturnLine:
    fields: dict[str, object] = {
        "id": uuid4(),
        "customer_return_id": document_id or uuid4(),
        "sales_invoice_line_id": uuid4(),
        "product_id": uuid4(),
        "device_unit_id": uuid4(),
        "quantity": 1,
        "currency": Currency.USD,
        "tracking_type": TrackingType.SERIAL,
        "charged_price": usd("520"),
        "sold_quantity": 1,
        "refund_price": usd("520"),
    }
    fields.update(overrides)
    return CustomerReturnLine(**fields)  # type: ignore[arg-type]


def a_return(**overrides: object) -> CustomerReturn:
    fields: dict[str, object] = {
        "id": uuid4(),
        "number": "CR-2026-0001",
        "status": DocumentStatus.DRAFT,
        "sales_invoice_id": uuid4(),
        "customer_id": uuid4(),
        "location_id": uuid4(),
        "reason": CustomerReturnReason.DEFECTIVE,
        "created_by": USER,
        "created_at": NOW,
    }
    fields.update(overrides)
    return CustomerReturn(**fields)  # type: ignore[arg-type]


class TestTheRefundIsCappedAtWhatTheSaleTook:
    """FR-4.9c: a return gives money back, it never gives money away."""

    def test_refunding_the_full_charge_is_the_default(self):
        line = a_line()

        assert line.refund_price == usd("520")
        assert not line.is_reduced

    def test_refunding_more_than_the_charge_is_refused(self):
        with pytest.raises(RefundExceedsChargeError):
            a_line(charged_price=usd("520"), refund_price=usd("600"))

    def test_a_negative_refund_is_refused(self):
        with pytest.raises(InvalidMoneyError):
            a_line(refund_price=Money(-100, Currency.USD))

    def test_a_refund_in_another_currency_is_refused(self):
        with pytest.raises(CurrencyMismatchError):
            a_line(refund_price=uzs("520"))

    def test_a_zero_refund_is_allowed_with_an_approver(self):
        """The store keeps the lot: a real case, not a rounding artefact."""
        line = a_line(
            refund_price=usd("0"),
            refund_approved_by=USER,
            refund_note="water damage",
        )

        assert line.refund_price.is_zero
        assert line.is_reduced


class TestAReducedRefundCarriesAName:
    """FR-4.9c: keeping part of a customer's money is somebody's decision."""

    def test_a_reduction_with_no_approver_is_refused(self):
        with pytest.raises(UnapprovedRefundError):
            a_line(refund_price=usd("468"), refund_note="opened box")

    def test_a_reduction_with_no_note_is_refused(self):
        with pytest.raises(UnapprovedRefundError):
            a_line(refund_price=usd("468"), refund_approved_by=USER)

    def test_reduce_to_stamps_both(self):
        line = a_line()

        line.reduce_to(usd("468"), USER, "opened box, 10% restocking")

        assert line.refund_price == usd("468")
        assert line.refund_approved_by == USER
        assert line.refund_note == "opened box, 10% restocking"
        assert line.is_reduced

    def test_reduce_to_above_the_charge_is_still_refused(self):
        line = a_line()

        with pytest.raises(RefundExceedsChargeError):
            line.reduce_to(usd("600"), USER, "generous")


class TestALineCannotReturnMoreThanWasSold:
    """FR-4.9b, as far as one line can state it on its own."""

    def test_returning_three_of_two_sold_is_refused(self):
        with pytest.raises(InvalidLineError):
            a_line(
                device_unit_id=None,
                tracking_type=TrackingType.QUANTITY,
                quantity=3,
                sold_quantity=2,
            )

    def test_returning_two_of_three_sold_is_fine(self):
        line = a_line(
            device_unit_id=None,
            tracking_type=TrackingType.QUANTITY,
            quantity=2,
            sold_quantity=3,
        )

        assert line.quantity == 2

    def test_a_serialized_line_names_its_handset(self):
        with pytest.raises(InvalidLineError):
            a_line(device_unit_id=None)

    def test_a_quantity_line_names_no_handset(self):
        with pytest.raises(InvalidLineError):
            a_line(tracking_type=TrackingType.QUANTITY, sold_quantity=3)

    def test_a_serialized_line_returns_exactly_one(self):
        with pytest.raises(InvalidLineError):
            a_line(quantity=2, sold_quantity=2)

    def test_counting_a_quantity_line_up_is_allowed(self):
        line = a_line(
            device_unit_id=None,
            tracking_type=TrackingType.QUANTITY,
            quantity=1,
            sold_quantity=3,
        )

        line.count(3)

        assert line.quantity == 3

    def test_counting_past_what_was_sold_leaves_the_line_alone(self):
        line = a_line(
            device_unit_id=None,
            tracking_type=TrackingType.QUANTITY,
            quantity=2,
            sold_quantity=3,
        )

        with pytest.raises(InvalidLineError):
            line.count(4)

        assert line.quantity == 2

    def test_a_serialized_line_has_no_count_to_correct(self):
        line = a_line()

        with pytest.raises(InvalidLineError):
            line.count(2)


class TestTheSubtotalsAreNeverSummed:
    """FR-2.7: one figure per currency present, never a combined total."""

    def test_a_phone_and_an_accessory_report_two_figures(self):
        document = a_return()
        document.lines = [
            a_line(document.id, refund_price=usd("520"), charged_price=usd("520")),
            a_line(
                document.id,
                device_unit_id=None,
                tracking_type=TrackingType.QUANTITY,
                currency=Currency.UZS,
                quantity=2,
                sold_quantity=2,
                charged_price=uzs("50000"),
                refund_price=uzs("50000"),
            ),
        ]

        assert document.subtotals() == {
            Currency.USD: usd("520"),
            Currency.UZS: uzs("100000"),
        }


class TestConfirmingTheReturn:
    def test_a_return_with_no_lines_confirms_nothing(self):
        document = a_return()

        with pytest.raises(EmptyDocumentError):
            document.confirm(NOW, USER)

    def test_the_same_handset_twice_is_refused(self):
        document = a_return()
        unit_id = uuid4()
        document.lines = [
            a_line(document.id, device_unit_id=unit_id),
            a_line(document.id, device_unit_id=unit_id),
        ]

        with pytest.raises(DuplicateScanError):
            document.confirm(NOW, USER)

    def test_a_confirmed_return_takes_no_more_scans(self):
        document = a_return()
        document.lines = [a_line(document.id)]
        document.confirm(NOW, USER)

        with pytest.raises(DocumentNotDraftError):
            document.assert_editable()

    def test_confirming_stamps_who_and_when(self):
        document = a_return()
        document.lines = [a_line(document.id)]

        document.confirm(NOW, USER)

        assert document.status is DocumentStatus.CONFIRMED
        assert document.confirmed_at == NOW
        assert document.confirmed_by == USER


class TestDebtReliefIsAlwaysSom:
    """§4.7, FR-4.9d: no rate exists, so relief is stated in som directly."""

    def test_relief_in_dollars_is_refused(self):
        document = a_return(debt_relief=usd("520"))
        document.lines = [a_line(document.id)]

        with pytest.raises(DebtReliefError):
            document.confirm(NOW, USER)

    def test_zero_relief_settles_nothing_and_is_refused(self):
        document = a_return(debt_relief=uzs("0"))
        document.lines = [a_line(document.id)]

        with pytest.raises(DebtReliefError):
            document.confirm(NOW, USER)

    def test_som_relief_confirms(self):
        document = a_return(debt_relief=uzs("2000000"))
        document.lines = [a_line(document.id)]

        document.confirm(NOW, USER)

        assert document.debt_relief == uzs("2000000")

    def test_no_relief_at_all_is_the_ordinary_case(self):
        document = a_return()
        document.lines = [a_line(document.id)]

        document.confirm(NOW, USER)

        assert document.debt_relief is None
