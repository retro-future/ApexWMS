"""What M8's payloads omit and never merge — FR-1.7, FR-2.11, PRD §5.9.

These run against the payload classes rather than the handlers, on purpose.
The rows themselves are covered end to end against real tables in
``tests/api/``; what cannot be reached through HTTP is the *shaping*, since
every role that holds ``Reporting.View`` today also holds ``Cost.View``
(§2.1). A custom role granting one without the other is exactly what
FR-1.7's omission has to survive, so it is asserted here where the two
permissions can be pulled apart.
"""

from datetime import UTC, datetime
from uuid import uuid4

from application.dtos import (
    AgeingRow,
    DeviceInventoryRow,
    NeedsPricingRow,
    SalesFigures,
    StockGroupBy,
    StockOnHandGroup,
)
from application.models import (
    AgeingRowData,
    DeviceInventoryRowData,
    NeedsPricingRowData,
    SalesFiguresData,
    StockOnHandData,
)
from domain.enums import DeviceCondition, DeviceStatus
from domain.value_objects import Currency, CurrencyTotals, Money

NOW = datetime(2026, 3, 1, tzinfo=UTC)
RECEIVED = datetime(2026, 1, 1, tzinfo=UTC)


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def uzs(major: str) -> Money:
    return Money.from_major(major, Currency.UZS)


def an_ageing_row(asking: Money | None = None) -> AgeingRow:
    return AgeingRow(
        device_unit_id=uuid4(),
        imei="490154203237518",
        product_id=uuid4(),
        sku="IP15P-256",
        product_name="iPhone 15 Pro",
        brand="Apple",
        condition=DeviceCondition.USED,
        location_id=uuid4(),
        location_name="Chilonzor shop",
        created_at=RECEIVED,
        acquisition_cost=usd("380"),
        asking_price=asking,
        markdown_count=2,
    )


def a_device_inventory_row(
    *,
    asking: Money | None = None,
    catalog: Money | None = None,
    condition: DeviceCondition = DeviceCondition.USED,
    status: DeviceStatus = DeviceStatus.IN_STOCK,
    was_returned: bool = False,
) -> DeviceInventoryRow:
    return DeviceInventoryRow(
        device_unit_id=uuid4(),
        imei="490154203237518",
        imei2=None,
        serial_number=None,
        product_id=uuid4(),
        sku="IP15P-256",
        product_name="iPhone 15 Pro",
        brand="Apple",
        condition=condition,
        status=status,
        was_customer_returned=was_returned,
        location_id=uuid4(),
        location_name="Chilonzor shop",
        created_at=RECEIVED,
        acquisition_cost=usd("380"),
        asking_price=asking,
        catalog_price=catalog,
        source_document_type=None,
        source_document_id=None,
    )


class TestTheDeviceInventoryRow:
    def test_cost_and_margin_are_absent_without_the_permission(self):
        row = DeviceInventoryRowData.from_entity(
            a_device_inventory_row(asking=usd("500")), NOW, show_cost=False
        )

        assert row.acquisition_cost is None
        assert row.implied_margin_minor is None
        assert row.resolved_price_minor == 50000
        assert row.days_in_stock == 59

    def test_the_margin_is_the_difference_with_the_permission(self):
        row = DeviceInventoryRowData.from_entity(
            a_device_inventory_row(asking=usd("500")), NOW, show_cost=True
        )

        assert row.acquisition_cost_minor == 38000
        assert row.implied_margin_minor == 12000

    def test_a_new_unit_falls_back_to_the_catalog_price(self):
        row = DeviceInventoryRowData.from_entity(
            a_device_inventory_row(
                asking=None, catalog=usd("900"), condition=DeviceCondition.NEW
            ),
            NOW,
            show_cost=True,
        )

        assert row.asking_price is None
        assert row.resolved_price_minor == 90000
        assert row.implied_margin_minor == 52000

    def test_a_used_unit_does_not_inherit_the_catalog_price(self):
        row = DeviceInventoryRowData.from_entity(
            a_device_inventory_row(asking=None, catalog=usd("900")),
            NOW,
            show_cost=True,
        )

        assert row.resolved_price is None
        assert row.implied_margin is None

    def test_a_returned_unit_carries_the_flag_while_its_status_is_in_stock(self):
        row = DeviceInventoryRowData.from_entity(
            a_device_inventory_row(was_returned=True), NOW, show_cost=False
        )

        assert row.status == "in_stock"
        assert row.was_customer_returned is True


class TestTheAgeingReportWithoutCostView:
    def test_the_cost_and_the_margin_are_absent_rather_than_zero(self):
        row = AgeingRowData.from_entity(
            an_ageing_row(usd("500")), NOW, show_cost=False
        )

        assert row.acquisition_cost is None
        assert row.acquisition_cost_minor is None
        assert row.implied_margin is None
        assert row.implied_margin_minor is None

    def test_what_survives_is_still_worth_reading(self):
        """The asking price and the markdown count are not costs, so the
        report still says *this has been cut twice and is still here*."""
        row = AgeingRowData.from_entity(
            an_ageing_row(usd("500")), NOW, show_cost=False
        )

        assert row.asking_price_minor == 50000
        assert row.markdown_count == 2
        assert row.days_in_stock == 59

    def test_with_the_permission_the_margin_is_the_difference(self):
        row = AgeingRowData.from_entity(an_ageing_row(usd("500")), NOW, show_cost=True)

        assert row.acquisition_cost_minor == 38000
        assert row.implied_margin_minor == 12000

    def test_an_unpriced_handset_implies_no_margin_even_with_the_permission(self):
        """Zero would read as a margin. There is not one to report."""
        row = AgeingRowData.from_entity(an_ageing_row(None), NOW, show_cost=True)

        assert row.asking_price is None
        assert row.implied_margin is None
        assert row.acquisition_cost_minor == 38000


class TestStockOnHandWithoutCostView:
    def group(self) -> StockOnHandGroup:
        return StockOnHandGroup(
            group_by=StockGroupBy.LOCATION,
            key=uuid4(),
            label="Chilonzor shop",
            quantity=11,
            cost_value=CurrencyTotals.empty().add(usd("700")).add(uzs("300000")),
        )

    def test_the_value_is_absent_and_the_count_is_not(self):
        """FR-9.1 puts the cost value behind the permission, not the shelf
        count — a Storekeeper may still be told what is on the shelf."""
        row = StockOnHandData.from_entity(self.group(), show_cost=False)

        assert row.cost_value is None
        assert row.quantity == 11

    def test_with_the_permission_the_two_currencies_stay_apart(self):
        row = StockOnHandData.from_entity(self.group(), show_cost=True)

        assert row.cost_value is not None
        assert [(one.currency, one.amount_minor) for one in row.cost_value] == [
            (Currency.USD, 70000),
            (Currency.UZS, 300000),
        ]


class TestNoReportEverMergesTwoCurrencies:
    """FR-2.11: every monetary total is grouped by currency and presented
    per currency. There is no field to write a combined figure into."""

    def test_the_sales_summary_reports_two_margins_and_no_sum(self):
        figures = SalesFiguresData.from_entity(
            SalesFigures(
                units_sold=3,
                revenue=CurrencyTotals.empty().add(usd("600")).add(uzs("50000")),
                cost_of_goods=CurrencyTotals.empty()
                .add(usd("-380"))
                .add(uzs("-30000")),
            )
        )

        assert {(one.currency, one.amount_minor) for one in figures.margin} == {
            (Currency.USD, 22000),
            (Currency.UZS, 20000),
        }
        assert not hasattr(figures, "total")

    def test_a_currency_present_on_only_one_side_still_reports_a_margin(self):
        """A sale with no COGS behind it is a margin worth seeing, not a row
        to drop."""
        figures = SalesFiguresData.from_entity(
            SalesFigures(revenue=CurrencyTotals.empty().add(uzs("50000")))
        )

        assert [(one.currency, one.amount_minor) for one in figures.margin] == [
            (Currency.UZS, 50000)
        ]

    def test_adding_a_dollar_to_a_som_total_is_not_expressible(self):
        totals = CurrencyTotals.empty().add(usd("600")).add(uzs("50000"))

        assert totals.of(Currency.USD) == usd("600")
        assert totals.of(Currency.UZS) == uzs("50000")
        assert totals.currencies == {Currency.USD, Currency.UZS}


class TestTheNeedsPricingWorklistCarriesNoMoneyAtAll:
    def test_no_field_on_it_is_a_cost_or_a_price(self):
        """The list exists so an Owner or Manager prices a handset. Neither
        the cost nor the asking price it does not have belongs on it."""
        row = NeedsPricingRowData.from_entity(
            NeedsPricingRow(
                device_unit_id=uuid4(),
                imei="490154203237518",
                product_id=uuid4(),
                sku="IP15P-256",
                product_name="iPhone 15 Pro",
                brand="Apple",
                condition=DeviceCondition.USED,
                location_id=uuid4(),
                location_name="Chilonzor shop",
                created_at=RECEIVED,
            ),
            NOW,
        )

        assert set(type(row).model_fields) == {
            "device_unit_id",
            "imei",
            "product_id",
            "sku",
            "product_name",
            "brand",
            "condition",
            "location_id",
            "location_name",
            "since",
            "days_unpriced",
            "reason",
        }
        assert row.reason == "used_no_price"
        assert row.days_unpriced == 59
