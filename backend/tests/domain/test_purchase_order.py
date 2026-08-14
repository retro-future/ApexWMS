"""``PurchaseOrder.confirm()`` — PRD §4.4, FR-3.1, FR-3.2.

A line may be raised with no price at all: the store may not know it until
it agrees one with the supplier. ``confirm`` is the point that requires
every line to state one, the same shape ``GoodsReceipt.confirm()`` already
enforces for its units.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.entities import PurchaseOrder, PurchaseOrderLine
from domain.enums import DocumentStatus, TrackingType
from domain.errors import (
    CurrencyMismatchError,
    DocumentNotDraftError,
    InvalidMoneyError,
    UnpricedOrderLineError,
)
from domain.value_objects import Currency, Money

NOW = datetime(2026, 8, 12, tzinfo=UTC)


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def order(**overrides) -> PurchaseOrder:
    return PurchaseOrder(
        number="PO-2026-0001",
        status=DocumentStatus.DRAFT,
        created_by=uuid4(),
        created_at=NOW,
        supplier_id=uuid4(),
        **overrides,
    )


def line(doc: PurchaseOrder, **overrides) -> PurchaseOrderLine:
    entry = PurchaseOrderLine(
        purchase_order_id=doc.id,
        product_id=overrides.pop("product_id", uuid4()),
        quantity=overrides.pop("quantity", 1),
        tracking_type=overrides.pop("tracking_type", TrackingType.SERIAL),
        currency=overrides.pop("currency", Currency.USD),
        **overrides,
    )
    doc.lines.append(entry)
    return entry


class TestRaisingALine:
    def test_a_line_may_be_raised_with_no_price(self):
        doc = order()
        entry = line(doc)

        assert entry.unit_cost is None
        assert entry.total_cost is None

    def test_a_negative_cost_is_refused(self):
        doc = order()

        with pytest.raises(InvalidMoneyError):
            line(doc, unit_cost=Money(-100, Currency.USD))

    def test_a_cost_in_the_wrong_currency_is_refused(self):
        doc = order()

        with pytest.raises(CurrencyMismatchError):
            line(doc, currency=Currency.UZS, unit_cost=usd("700"))


class TestConfirmRequiresEveryLinePriced:
    def test_an_unpriced_line_refuses_to_confirm(self):
        doc = order()
        line(doc, quantity=3)

        with pytest.raises(UnpricedOrderLineError):
            doc.confirm(NOW, uuid4())

        assert doc.status is DocumentStatus.DRAFT

    def test_every_offending_product_is_named_in_one_message(self):
        doc = order()
        a = line(doc)
        b = line(doc)
        line(doc, unit_cost=usd("700"))

        with pytest.raises(UnpricedOrderLineError) as excinfo:
            doc.confirm(NOW, uuid4())

        assert str(a.product_id) in str(excinfo.value)
        assert str(b.product_id) in str(excinfo.value)

    def test_a_fully_priced_order_confirms(self):
        doc = order()
        line(doc, unit_cost=usd("700"), quantity=2)

        doc.confirm(NOW, uuid4())

        assert doc.status is DocumentStatus.CONFIRMED

    def test_a_confirmed_order_cannot_be_confirmed_again(self):
        doc = order()
        line(doc, unit_cost=usd("700"))
        doc.confirm(NOW, uuid4())

        with pytest.raises(DocumentNotDraftError):
            doc.confirm(NOW, uuid4())


class TestSubtotals:
    def test_an_unpriced_line_is_skipped_rather_than_refused(self):
        """A draft is read while it is still being filled in."""
        doc = order()
        line(doc, unit_cost=usd("600"), quantity=1)
        line(doc)

        assert doc.subtotals() == {Currency.USD: usd("600")}

    def test_one_subtotal_per_currency_and_no_sum(self):
        doc = order()
        line(doc, currency=Currency.USD, unit_cost=usd("600"), quantity=1)
        line(
            doc,
            currency=Currency.UZS,
            unit_cost=Money.from_major("10000", Currency.UZS),
            quantity=5,
            tracking_type=TrackingType.QUANTITY,
        )

        assert doc.subtotals() == {
            Currency.USD: usd("600"),
            Currency.UZS: Money.from_major("50000", Currency.UZS),
        }
