"""``GoodsReceipt.confirm()`` — PRD §7.4 point 3, FR-3.3b, FR-3.8, FR-3.10.

Every rule here is a pure function of the receipt's own lines: no catalog,
no database, no tenant. That is the claim §7.4 makes about this aggregate,
and this module is what holds it to it — nothing below imports a
repository or awaits anything.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.entities import GoodsReceipt, GoodsReceiptLine, ReceivedUnit
from domain.enums import (
    AcquisitionSource,
    DeviceCondition,
    DocumentStatus,
    TrackingType,
)
from domain.errors import (
    CurrencyMismatchError,
    DocumentNotConfirmedError,
    DocumentNotDraftError,
    DuplicateScanError,
    InvalidLineError,
    InvalidMoneyError,
    ReceiptIncompleteError,
    ReceiptSourceError,
    UnpricedUnitError,
)
from domain.value_objects import IMEI, Currency, Money

NOW = datetime(2026, 8, 11, tzinfo=UTC)
IMEIS = ["490154203237518", "356938035643809", "352099001761481", "013269009999998"]


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def uzs(major: str) -> Money:
    return Money.from_major(major, Currency.UZS)


def receipt(
    source: AcquisitionSource = AcquisitionSource.SUPPLIER,
    *,
    supplier_id=None,
    **overrides,
) -> GoodsReceipt:
    if source is AcquisitionSource.SUPPLIER and supplier_id is None:
        supplier_id = uuid4()
    return GoodsReceipt(
        number="GR-2026-0001",
        status=DocumentStatus.DRAFT,
        created_by=uuid4(),
        created_at=NOW,
        acquisition_source=source,
        supplier_id=supplier_id,
        location_id=uuid4(),
        **overrides,
    )


def serial_line(doc: GoodsReceipt, quantity: int = 1, **overrides) -> GoodsReceiptLine:
    line = GoodsReceiptLine(
        goods_receipt_id=doc.id,
        product_id=overrides.pop("product_id", uuid4()),
        quantity=quantity,
        tracking_type=TrackingType.SERIAL,
        currency=overrides.pop("currency", Currency.USD),
        **overrides,
    )
    doc.lines.append(line)
    return line


def quantity_line(doc: GoodsReceipt, quantity: int = 10, **overrides) -> GoodsReceiptLine:
    line = GoodsReceiptLine(
        goods_receipt_id=doc.id,
        product_id=uuid4(),
        quantity=quantity,
        tracking_type=TrackingType.QUANTITY,
        currency=overrides.pop("currency", Currency.UZS),
        **overrides,
    )
    doc.lines.append(line)
    return line


def scan(
    line: GoodsReceiptLine,
    imei: str = IMEIS[0],
    condition: DeviceCondition = DeviceCondition.NEW,
    cost: Money | None = None,
    asking: Money | None = None,
    **overrides,
) -> ReceivedUnit:
    unit = ReceivedUnit(
        goods_receipt_line_id=line.id,
        imei=IMEI(imei),
        condition=condition,
        acquisition_cost=cost if cost is not None else usd("700"),
        asking_price=asking,
        **overrides,
    )
    line.units.append(unit)
    return unit


class TestWhereTheGoodsCameFrom:
    """FR-3.3b's three stated cases."""

    def test_a_trade_in_needs_no_supplier(self):
        doc = receipt(AcquisitionSource.TRADE_IN)
        line = serial_line(doc)
        scan(
            line,
            condition=DeviceCondition.USED,
            cost=usd("330"),
            asking=usd("420"),
            cash_paid_minor=4_000_000,
            cash_paid_currency=Currency.UZS,
        )

        doc.confirm(NOW, uuid4())

        assert doc.status is DocumentStatus.CONFIRMED
        assert doc.supplier_id is None

    def test_a_supplier_receipt_without_a_supplier_is_rejected_when_it_is_built(self):
        with pytest.raises(ReceiptSourceError, match="must name one"):
            GoodsReceipt(
                number="GR-2026-0002",
                status=DocumentStatus.DRAFT,
                created_by=uuid4(),
                created_at=NOW,
                acquisition_source=AcquisitionSource.SUPPLIER,
                location_id=uuid4(),
            )

    def test_a_trade_in_cannot_be_linked_to_a_purchase_order(self):
        with pytest.raises(ReceiptSourceError, match="walked in the door"):
            receipt(AcquisitionSource.TRADE_IN, purchase_order_id=uuid4())

    def test_a_trade_in_cannot_name_a_supplier(self):
        with pytest.raises(ReceiptSourceError):
            receipt(AcquisitionSource.TRADE_IN, supplier_id=uuid4())


class TestUsedStockIsIndependentOfTheSource:
    """The point the whole enum rests on: ``condition`` is about the
    handset, ``acquisition_source`` is about the delivery, and no rule ties
    them together."""

    def test_a_supplier_delivers_new_and_used_handsets_on_one_receipt(self):
        doc = receipt(AcquisitionSource.SUPPLIER)
        line = serial_line(doc, quantity=3)
        scan(line, IMEIS[0], DeviceCondition.NEW, usd("700"))
        scan(line, IMEIS[1], DeviceCondition.USED, usd("410"), usd("520"))
        scan(line, IMEIS[2], DeviceCondition.REFURBISHED, usd("480"), usd("580"))

        doc.confirm(NOW, uuid4())

        assert doc.status is DocumentStatus.CONFIRMED

    def test_a_walk_in_can_bring_in_a_sealed_handset(self):
        doc = receipt(AcquisitionSource.TRADE_IN, customer_id=uuid4())
        scan(
            serial_line(doc),
            condition=DeviceCondition.NEW,
            cost=usd("650"),
            cash_paid_minor=8_000_000,
            cash_paid_currency=Currency.UZS,
        )

        doc.confirm(NOW, uuid4())

        assert doc.status is DocumentStatus.CONFIRMED


class TestWhatWasHandedOverForATradeIn:
    """W9 B2: the som leaves no trace anywhere else, so it is required."""

    def test_a_trade_in_without_the_som_cannot_be_confirmed(self):
        doc = receipt(AcquisitionSource.TRADE_IN)
        scan(serial_line(doc), condition=DeviceCondition.USED,
             cost=usd("330"), asking=usd("420"))

        with pytest.raises(UnpricedUnitError, match="no cash paid"):
            doc.confirm(NOW, uuid4())

    def test_a_supplier_receipt_never_asks_for_it(self):
        doc = receipt(AcquisitionSource.SUPPLIER)
        scan(serial_line(doc), cost=usd("700"))

        doc.confirm(NOW, uuid4())

        assert doc.status is DocumentStatus.CONFIRMED

    def test_the_message_names_every_handset_missing_it(self):
        doc = receipt(AcquisitionSource.TRADE_IN)
        line = serial_line(doc, quantity=2)
        scan(line, IMEIS[0], DeviceCondition.USED, usd("330"), usd("420"),
             cash_paid_minor=4_000_000, cash_paid_currency=Currency.UZS)
        scan(line, IMEIS[1], DeviceCondition.USED, usd("300"), usd("390"))

        with pytest.raises(UnpricedUnitError, match=IMEIS[1]):
            doc.confirm(NOW, uuid4())


class TestEveryHandsetIsAccountedFor:
    def test_a_short_scanned_line_cannot_be_confirmed(self):
        """FR-3.8, and the message says how short it is."""
        doc = receipt()
        line = serial_line(doc, quantity=3)
        scan(line, IMEIS[0])
        scan(line, IMEIS[1])

        with pytest.raises(ReceiptIncompleteError, match="2 of 3 scanned"):
            doc.confirm(NOW, uuid4())

    def test_the_same_handset_cannot_be_scanned_twice(self):
        doc = receipt()
        line = serial_line(doc, quantity=2)
        scan(line, IMEIS[0])
        scan(line, IMEIS[0])

        with pytest.raises(DuplicateScanError, match=IMEIS[0]):
            doc.confirm(NOW, uuid4())

    def test_a_receipt_with_no_lines_receives_nothing(self):
        with pytest.raises(ReceiptIncompleteError, match="no lines"):
            receipt().confirm(NOW, uuid4())


class TestNothingUnpricedReachesTheShelf:
    def test_a_used_handset_with_no_asking_price_is_named(self):
        """FR-3.10's stated test: two units, one NEW and one USED with no
        price. The refusal names only the used one."""
        doc = receipt()
        line = serial_line(doc, quantity=2)
        scan(line, IMEIS[0], DeviceCondition.NEW, usd("700"))
        scan(line, IMEIS[1], DeviceCondition.USED, usd("410"))

        with pytest.raises(UnpricedUnitError) as refused:
            doc.confirm(NOW, uuid4())

        assert IMEIS[1] in str(refused.value)
        assert IMEIS[0] not in str(refused.value)

        line.units[1].asking_price = usd("520")
        doc.confirm(NOW, uuid4())
        assert doc.status is DocumentStatus.CONFIRMED

    def test_every_offending_handset_is_named_in_one_message(self):
        """The gap is closed in one pass, not one round trip per phone."""
        doc = receipt()
        line = serial_line(doc, quantity=3)
        scan(line, IMEIS[0], DeviceCondition.USED, usd("410"))
        scan(line, IMEIS[1], DeviceCondition.REFURBISHED, usd("480"))
        scan(line, IMEIS[2], DeviceCondition.NEW, usd("700"))

        with pytest.raises(UnpricedUnitError) as refused:
            doc.confirm(NOW, uuid4())

        assert IMEIS[0] in str(refused.value) and IMEIS[1] in str(refused.value)

    def test_a_handset_with_no_cost_cannot_be_confirmed(self):
        doc = receipt()
        line = serial_line(doc)
        line.units.append(
            ReceivedUnit(
                goods_receipt_line_id=line.id,
                imei=IMEI(IMEIS[0]),
                condition=DeviceCondition.NEW,
            )
        )

        with pytest.raises(UnpricedUnitError, match="no acquisition cost"):
            doc.confirm(NOW, uuid4())

    def test_a_quantity_line_with_no_unit_cost_cannot_be_confirmed(self):
        doc = receipt()
        quantity_line(doc, quantity=10)

        with pytest.raises(UnpricedUnitError, match="no unit cost"):
            doc.confirm(NOW, uuid4())

    def test_a_draft_may_sit_unpriced_indefinitely(self):
        """FR-3.12: the completeness checks run at confirm, not at scan."""
        doc = receipt()
        line = serial_line(doc, quantity=2)
        scan(line, IMEIS[0], DeviceCondition.USED, usd("410"))

        assert doc.status is DocumentStatus.DRAFT
        assert [u.needs_asking_price for u in line.units] == [True]


class TestOneCurrencyPerLine:
    def test_a_receipt_reports_one_subtotal_per_currency_and_no_sum(self):
        """FR-2.7: a USD phone and a UZS accessory on one document."""
        doc = receipt()
        phones = serial_line(doc, currency=Currency.USD)
        scan(phones, IMEIS[0], DeviceCondition.NEW, usd("600"))
        quantity_line(doc, quantity=5, currency=Currency.UZS, unit_cost=uzs("10000"))

        doc.confirm(NOW, uuid4())

        assert doc.subtotals() == {Currency.USD: usd("600"), Currency.UZS: uzs("50000")}

    def test_a_line_cost_in_the_wrong_currency_is_refused(self):
        doc = receipt()
        with pytest.raises(CurrencyMismatchError):
            quantity_line(doc, currency=Currency.UZS, unit_cost=usd("10"))

    def test_a_serialized_line_carries_no_line_cost(self):
        doc = receipt()
        with pytest.raises(InvalidLineError, match="individually"):
            serial_line(doc, unit_cost=usd("700"))


class TestTheLifecycle:
    def test_a_confirmed_receipt_cannot_be_confirmed_again(self):
        doc = receipt()
        scan(serial_line(doc))
        doc.confirm(NOW, uuid4())

        with pytest.raises(DocumentNotDraftError):
            doc.confirm(NOW, uuid4())

    def test_a_draft_cannot_be_cancelled(self):
        with pytest.raises(DocumentNotConfirmedError):
            receipt().cancel(NOW, uuid4())

    def test_a_receipt_cannot_be_cancelled_twice(self):
        """What stops the ledger reversal running twice — the poster holds
        no guard of its own (§4.3 rule 2)."""
        doc = receipt()
        scan(serial_line(doc))
        actor = uuid4()
        doc.confirm(NOW, actor)
        doc.cancel(NOW, actor, "wrong supplier")

        with pytest.raises(DocumentNotConfirmedError):
            doc.cancel(NOW, actor)

    def test_cancelling_keeps_the_note_it_was_raised_with(self):
        doc = receipt(note="third delivery this week")
        scan(serial_line(doc))
        doc.confirm(NOW, uuid4())
        doc.cancel(NOW, uuid4(), "sent straight back")

        assert doc.note == "third delivery this week"
        assert doc.cancellation_reason == "sent straight back"


class TestTheInertCashPaidPair:
    def test_a_trade_in_records_what_was_handed_over(self):
        """§4.5b: booked in dollars, paid in som, and the two never meet."""
        doc = receipt(AcquisitionSource.TRADE_IN)
        line = serial_line(doc)
        scan(
            line,
            condition=DeviceCondition.USED,
            cost=usd("330"),
            asking=usd("420"),
            cash_paid_minor=4_200_000,
            cash_paid_currency=Currency.UZS,
        )

        doc.confirm(NOW, uuid4())

        assert doc.subtotals() == {Currency.USD: usd("330")}
        assert Currency.UZS not in doc.subtotals()

    def test_cash_paid_needs_both_halves_or_neither(self):
        doc = receipt()
        with pytest.raises(InvalidMoneyError, match="both an amount and a currency"):
            scan(serial_line(doc), cash_paid_minor=4_200_000)
