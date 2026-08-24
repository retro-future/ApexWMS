"""``SupplierReturn`` and ``WriteOff`` — PRD §5.5, §5.6, FR-5.1 to FR-6.5.

One suite for two documents, because they share ``RemovalLine`` and
therefore share every line rule: what a serialized line may say, what a
quantity line may not, and that one handset gets one line. Only the header
rules differ, and those get a class each at the bottom.

Whether a handset is *still on the shelf* is not here. That needs the live
unit, so FR-5.2 lives in ``RemovalScanner`` and ``RemovalPoster`` and is
tested against the application harness instead. Nothing below imports a
repository or awaits anything.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from domain.entities import (
    SupplierReturn,
    SupplierReturnLine,
    WriteOff,
    WriteOffLine,
)
from domain.enums import (
    DocumentStatus,
    SupplierReturnReason,
    TrackingType,
    WriteOffReason,
)
from domain.errors import (
    DocumentNotConfirmedError,
    DocumentNotDraftError,
    DuplicateScanError,
    EmptyDocumentError,
    InvalidLineError,
)
from domain.value_objects import Currency

NOW = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)


def return_line(document_id: UUID | None = None, **overrides: object) -> SupplierReturnLine:
    fields: dict[str, object] = {
        "id": uuid4(),
        "supplier_return_id": document_id or uuid4(),
        "product_id": uuid4(),
        "device_unit_id": uuid4(),
        "quantity": 1,
        "currency": Currency.USD,
        "tracking_type": TrackingType.SERIAL,
    }
    fields.update(overrides)
    return SupplierReturnLine(**fields)  # type: ignore[arg-type]


def write_off_line(document_id: UUID | None = None, **overrides: object) -> WriteOffLine:
    fields: dict[str, object] = {
        "id": uuid4(),
        "write_off_id": document_id or uuid4(),
        "product_id": uuid4(),
        "device_unit_id": uuid4(),
        "quantity": 1,
        "currency": Currency.USD,
        "tracking_type": TrackingType.SERIAL,
    }
    fields.update(overrides)
    return WriteOffLine(**fields)  # type: ignore[arg-type]


def a_return(
    *lines: SupplierReturnLine, status: DocumentStatus = DocumentStatus.DRAFT
) -> SupplierReturn:
    return SupplierReturn(
        id=uuid4(),
        number="SR-2026-0001",
        status=status,
        supplier_id=uuid4(),
        location_id=uuid4(),
        reason=SupplierReturnReason.DEFECTIVE,
        created_by=uuid4(),
        created_at=NOW,
        lines=list(lines),
    )


def a_write_off(
    *lines: WriteOffLine, status: DocumentStatus = DocumentStatus.DRAFT
) -> WriteOff:
    return WriteOff(
        id=uuid4(),
        number="WO-2026-0001",
        status=status,
        location_id=uuid4(),
        reason=WriteOffReason.DAMAGE,
        created_by=uuid4(),
        created_at=NOW,
        lines=list(lines),
    )


class TestALineTakesItsShapeFromItsProduct:
    """The rules ``RemovalLine`` states once for both documents (§4.1)."""

    def test_a_serialized_line_names_the_handset_it_moves(self):
        with pytest.raises(InvalidLineError):
            return_line(device_unit_id=None)

    def test_a_serialized_line_moves_exactly_one(self):
        with pytest.raises(InvalidLineError):
            return_line(quantity=2)

    def test_a_quantity_line_names_no_handset(self):
        with pytest.raises(InvalidLineError):
            return_line(tracking_type=TrackingType.QUANTITY, quantity=3)

    def test_a_quantity_line_moves_several(self):
        line = return_line(
            tracking_type=TrackingType.QUANTITY, device_unit_id=None, quantity=3
        )
        assert line.quantity == 3
        assert line.is_serial is False

    def test_a_line_for_nothing_moves_nothing(self):
        with pytest.raises(InvalidLineError):
            return_line(quantity=0)

    def test_the_write_offs_line_obeys_the_same_rules(self):
        """Both inherit ``RemovalLine``, so this is the proof it is one rule
        and not two copies of one."""
        with pytest.raises(InvalidLineError):
            write_off_line(device_unit_id=None)


class TestOnePhoneOneLine:
    def test_a_return_refuses_the_same_handset_twice(self):
        unit_id = uuid4()
        document = a_return(
            return_line(device_unit_id=unit_id), return_line(device_unit_id=unit_id)
        )

        with pytest.raises(DuplicateScanError):
            document.confirm(NOW, uuid4())

    def test_a_write_off_refuses_the_same_handset_twice(self):
        unit_id = uuid4()
        document = a_write_off(
            write_off_line(device_unit_id=unit_id), write_off_line(device_unit_id=unit_id)
        )

        with pytest.raises(DuplicateScanError):
            document.confirm(NOW, uuid4())

    def test_two_quantity_lines_of_the_same_product_are_not_a_duplicate(self):
        """Neither names a handset, so there is nothing to be duplicated."""
        document = a_return(
            return_line(tracking_type=TrackingType.QUANTITY, device_unit_id=None),
            return_line(tracking_type=TrackingType.QUANTITY, device_unit_id=None),
        )

        document.confirm(NOW, uuid4())

        assert document.status is DocumentStatus.CONFIRMED

    def test_a_scanned_handset_is_found_by_its_line(self):
        unit_id = uuid4()
        line = return_line(device_unit_id=unit_id)
        document = a_return(line)

        assert document.line_for_unit(unit_id) is line
        assert document.line_for_unit(uuid4()) is None


class TestNothingIsMovedByAnEmptyDocument:
    def test_a_return_with_no_lines_is_refused(self):
        with pytest.raises(EmptyDocumentError):
            a_return().confirm(NOW, uuid4())

    def test_a_write_off_with_no_lines_is_refused(self):
        with pytest.raises(EmptyDocumentError):
            a_write_off().confirm(NOW, uuid4())


class TestTheSharedLifecycle:
    def test_confirming_stamps_who_and_when(self):
        document = a_return(return_line())
        actor = uuid4()

        document.confirm(NOW, actor)

        assert document.status is DocumentStatus.CONFIRMED
        assert document.confirmed_at == NOW
        assert document.confirmed_by == actor

    def test_a_confirmed_document_is_no_longer_editable(self):
        document = a_write_off(write_off_line())
        document.confirm(NOW, uuid4())

        with pytest.raises(DocumentNotDraftError):
            document.assert_editable()

    def test_a_draft_cannot_be_cancelled(self):
        """There is nothing to compensate: a draft wrote no ledger rows."""
        with pytest.raises(DocumentNotConfirmedError):
            a_return(return_line()).cancel(NOW, uuid4())

    def test_a_confirmed_document_cancels_once(self):
        document = a_return(return_line())
        document.confirm(NOW, uuid4())

        document.cancel(NOW, uuid4(), "the supplier would not take them")

        assert document.status is DocumentStatus.CANCELLED
        assert document.cancellation_reason == "the supplier would not take them"

    def test_and_never_twice(self):
        """Reversing a reversal would re-apply the document, and
        ``LedgerPoster.reverse`` holds no guard of its own."""
        document = a_write_off(write_off_line())
        document.confirm(NOW, uuid4())
        document.cancel(NOW, uuid4())

        with pytest.raises(DocumentNotConfirmedError):
            document.cancel(NOW, uuid4())


class TestAReturnAlwaysNamesASupplier:
    """FR-5.1: nothing goes back to a walk-in."""

    def test_a_return_carries_its_reason(self):
        document = a_return(return_line())
        assert document.reason is SupplierReturnReason.DEFECTIVE

    def test_the_reason_may_be_the_open_one(self):
        """``OTHER`` is not in FR-5.1's three, and exists so a real case
        never has to be filed under a wrong one."""
        document = a_return(return_line())
        document.reason = SupplierReturnReason.OTHER

        document.confirm(NOW, uuid4())

        assert document.status is DocumentStatus.CONFIRMED


class TestAWriteOffAlwaysNamesAReason:
    """FR-6.5: a loss the store cannot categorise is one it cannot learn from."""

    def test_theft_and_damage_are_different_findings(self):
        assert WriteOffReason.THEFT is not WriteOffReason.DAMAGE

    def test_a_write_off_carries_its_reason_through_the_confirm(self):
        document = a_write_off(write_off_line())
        document.reason = WriteOffReason.THEFT

        document.confirm(NOW, uuid4())

        assert document.reason is WriteOffReason.THEFT
