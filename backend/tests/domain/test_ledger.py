"""The two ledgers' own rules — PRD §4.3, §4.6.

Both are append-only, both name their cause and their author, and both
reverse by negation rather than deletion. These tests hold the *entities*
to that; ``tests/application/test_ledger_posting.py`` holds the service
that writes them to it.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from domain.entities import FinancialTransaction, StockLevel, StockMovement
from domain.enums import DeviceStatus, DocumentType, MovementType, TransactionType
from domain.errors import InvalidMoneyError, InvalidMovementError
from domain.services import UnitProjector
from domain.value_objects import Currency, Money

NOW = datetime(2026, 3, 1, tzinfo=UTC)
LATER = NOW + timedelta(hours=2)


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def movement(**overrides) -> StockMovement:
    fields = {
        "occurred_at": NOW,
        "movement_type": MovementType.RECEIPT,
        "product_id": uuid4(),
        "location_id": uuid4(),
        "quantity_delta": 5,
        "document_type": DocumentType.GOODS_RECEIPT,
        "document_id": uuid4(),
        "user_id": uuid4(),
    }
    return StockMovement(**{**fields, **overrides})


def transaction(**overrides) -> FinancialTransaction:
    fields = {
        "occurred_at": NOW,
        "txn_type": TransactionType.PURCHASE,
        "amount": usd("-500"),
        "document_type": DocumentType.GOODS_RECEIPT,
        "document_id": uuid4(),
        "user_id": uuid4(),
    }
    return FinancialTransaction(**{**fields, **overrides})


class TestAMovementRecordsSomethingChanging:
    def test_a_zero_delta_is_refused(self):
        with pytest.raises(InvalidMovementError):
            movement(quantity_delta=0)

    def test_a_serialized_movement_moves_exactly_one_handset(self):
        """The IMEI trace rests on a row naming *which* unit it meant."""
        with pytest.raises(InvalidMovementError):
            movement(device_unit_id=uuid4(), quantity_delta=2)

    def test_a_quantity_movement_may_move_any_number(self):
        assert movement(quantity_delta=200).quantity_delta == 200

    def test_a_serialized_movement_may_be_plus_or_minus_one(self):
        unit_id = uuid4()

        assert movement(device_unit_id=unit_id, quantity_delta=1).quantity_delta == 1
        assert movement(device_unit_id=unit_id, quantity_delta=-1).quantity_delta == -1


class TestReversalIsNegationAndNotDeletion:
    def test_a_reversed_movement_keeps_its_type_and_flips_its_sign(self):
        """§4.3 rule 2. The type is kept because a reversal of a sale is
        still part of that sale's story — and because a separate
        "reversal" category would have to be remembered, and excluded, by
        every report that groups by type."""
        sale = movement(movement_type=MovementType.SALE, quantity_delta=-1, device_unit_id=uuid4())
        canceller = uuid4()

        compensating = sale.reversed(LATER, canceller)

        assert compensating.movement_type is MovementType.SALE
        assert compensating.quantity_delta == 1
        assert compensating.document_id == sale.document_id
        assert compensating.occurred_at == LATER

    def test_a_reversal_names_whoever_cancelled_not_whoever_sold(self):
        """The two need not be the same person, and the ledger's job is to
        say who did what."""
        seller, manager = uuid4(), uuid4()
        sale = movement(user_id=seller, quantity_delta=-1, device_unit_id=uuid4())

        assert sale.reversed(LATER, manager).user_id == manager

    def test_a_movement_and_its_reversal_net_to_zero(self):
        sale = movement(quantity_delta=-3)

        assert sale.quantity_delta + sale.reversed(LATER, uuid4()).quantity_delta == 0

    def test_a_reversal_is_a_new_row_and_not_the_original(self):
        original = movement()

        assert original.reversed(LATER, uuid4()).id != original.id


class TestTheMoneyLedger:
    def test_a_zero_transaction_is_refused(self):
        with pytest.raises(InvalidMoneyError):
            transaction(amount=usd("0"))

    def test_direction_is_the_sign_of_the_amount(self):
        assert transaction(amount=usd("-500")).amount.is_negative
        assert not transaction(
            txn_type=TransactionType.SALE_REVENUE, amount=usd("600")
        ).amount.is_negative

    def test_a_transaction_and_its_reversal_net_to_zero(self):
        """FR-10.2's stated test at the entity level: both stay visible and
        the pair sums to nothing."""
        purchase = transaction(amount=usd("-500"))

        reversal = purchase.reversed(LATER, uuid4())

        assert purchase.amount + reversal.amount == usd("0")
        assert reversal.txn_type is purchase.txn_type
        assert reversal.document_id == purchase.document_id

    def test_a_transaction_reports_the_currency_it_was_booked_in(self):
        assert transaction().currency is Currency.USD
        assert transaction(
            amount=Money.from_major("-50000", Currency.UZS)
        ).currency is Currency.UZS


class TestTransactionCategories:
    @pytest.mark.parametrize(
        ("txn_type", "sign"),
        [
            (TransactionType.PURCHASE, -1),
            (TransactionType.SALE_REVENUE, +1),
            (TransactionType.COGS, -1),
            (TransactionType.WRITE_OFF_LOSS, -1),
            (TransactionType.SUPPLIER_RETURN_CREDIT, +1),
            (TransactionType.PAYMENT_RECEIVED, +1),
        ],
    )
    def test_each_category_knows_which_way_it_ordinarily_points(self, txn_type, sign):
        assert txn_type.ordinary_sign == sign

    def test_a_count_adjustment_has_no_ordinary_direction(self):
        """A physical count finds surplus as readily as shortage."""
        assert TransactionType.COUNT_ADJUSTMENT.ordinary_sign == 0

    def test_the_ordinary_sign_is_not_enforced_on_a_row(self):
        """Because a reversal must be allowed to contradict it — that is
        the whole mechanism by which a cancelled document nets to zero."""
        reversed_purchase = transaction(amount=usd("500"))

        assert reversed_purchase.txn_type.ordinary_sign == -1
        assert not reversed_purchase.amount.is_negative


class TestProjectingAHandsetsStateFromItsTimeline:
    """The one definition of "derived" (``domain/services/projection.py``),
    shared by the posting service and ``verify-projections`` — so a
    reported mismatch is always real and never two opinions."""

    def test_a_received_handset_is_in_stock_where_it_arrived(self):
        warehouse = uuid4()
        unit = uuid4()

        state = UnitProjector.project(
            [
                movement(
                    movement_type=MovementType.RECEIPT,
                    device_unit_id=unit,
                    quantity_delta=1,
                    location_id=warehouse,
                )
            ]
        )

        assert state == (DeviceStatus.IN_STOCK, warehouse)

    def test_a_sold_handset_is_sold_and_nowhere(self):
        unit, location = uuid4(), uuid4()

        state = UnitProjector.project(
            [
                movement(
                    movement_type=MovementType.RECEIPT,
                    device_unit_id=unit,
                    quantity_delta=1,
                    location_id=location,
                ),
                movement(
                    movement_type=MovementType.SALE,
                    device_unit_id=unit,
                    quantity_delta=-1,
                    location_id=location,
                ),
            ]
        )

        assert state == (DeviceStatus.SOLD, None)

    @pytest.mark.parametrize(
        ("gone_by", "status"),
        [
            (MovementType.SALE, DeviceStatus.SOLD),
            (MovementType.WRITE_OFF, DeviceStatus.WRITTEN_OFF),
            (MovementType.SUPPLIER_RETURN, DeviceStatus.RETURNED_TO_SUPPLIER),
            (MovementType.COUNT_ADJUSTMENT, DeviceStatus.WRITTEN_OFF),
        ],
    )
    def test_how_a_unit_left_decides_where_it_ended_up(self, gone_by, status):
        unit, location = uuid4(), uuid4()

        state = UnitProjector.project(
            [
                movement(
                    movement_type=MovementType.RECEIPT,
                    device_unit_id=unit,
                    quantity_delta=1,
                    location_id=location,
                ),
                movement(
                    movement_type=gone_by,
                    device_unit_id=unit,
                    quantity_delta=-1,
                    location_id=location,
                ),
            ]
        )

        assert state == (status, None)

    def test_a_cancelled_sale_puts_the_handset_back_on_the_shelf(self):
        """The compensating +1 is what the projection reads — no separate
        "this was a reversal" flag is consulted, because there isn't one."""
        unit, location = uuid4(), uuid4()
        sale = movement(
            movement_type=MovementType.SALE,
            device_unit_id=unit,
            quantity_delta=-1,
            location_id=location,
        )

        state = UnitProjector.project(
            [
                movement(
                    movement_type=MovementType.RECEIPT,
                    device_unit_id=unit,
                    quantity_delta=1,
                    location_id=location,
                ),
                sale,
                sale.reversed(LATER, uuid4()),
            ]
        )

        assert state == (DeviceStatus.IN_STOCK, location)

    def test_a_handset_with_no_history_has_no_state_to_project(self):
        with pytest.raises(ValueError):
            UnitProjector.project([])


class TestStockLevelIsAProjection:
    def test_a_level_cannot_go_negative(self):
        """FR-4.7 refuses a confirm that would oversell rather than booking
        the shortfall, so this state must never be reachable."""
        with pytest.raises(InvalidMovementError):
            StockLevel(product_id=uuid4(), location_id=uuid4(), quantity=-1)

    def test_zero_is_a_perfectly_good_level(self):
        level = StockLevel(product_id=uuid4(), location_id=uuid4(), quantity=0)

        assert level.quantity == 0
