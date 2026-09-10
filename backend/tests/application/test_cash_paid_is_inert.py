"""FR-3.4d: ``cash_paid`` enters no ledger, no total, and no report figure.

**This suite exists to catch a future report quietly summing it.** §4.5b
is explicit that the field is deliberately denormalized, deliberately
inert, and exists only to be read one row at a time — *"any report that
adds ``cash_paid`` to anything is a bug"*.

The method is the one FR-3.4d prescribes: compute everything twice, once
with the som figure recorded and once with it cleared, and assert the two
runs are identical. A figure that leaks into a total cannot survive that.
"""

from datetime import UTC, datetime
from uuid import uuid4

from application.dtos import AgeingRow, MoneyEffect, Posting, PostingEntry
from application.models import (
    AgeingRowData,
    DeviceUnitData,
    FinancialLedgerRowData,
    MovementRowData,
    NeedsPricingRowData,
    SalesFiguresData,
    StockOnHandData,
)
from application.services import LedgerReconciler
from domain.entities import DeviceUnit, Product
from domain.enums import (
    DeviceCondition,
    DeviceStatus,
    DocumentType,
    MovementType,
    TrackingType,
    TransactionType,
)
from domain.value_objects import IMEI, SKU, Currency, Money
from tests.application.builders import make_world

NOW = datetime(2026, 3, 1, tzinfo=UTC)
IMEI_A = "490154203237518"
# The §4.5b worked example: a handset bought from a walk-in for som and
# booked at the dollar figure the owner had in mind when they made the offer.
BOOKED = "330"
CASH_PAID_SOM = 4_200_000


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


async def trade_in_store(*, record_cash: bool):
    """A store holding one som-paid trade-in, with and without the record."""
    world = make_world()
    location = uuid4()
    product = Product(
        sku=SKU("IP11-64"),
        name="iPhone 11 64GB",
        tracking_type=TrackingType.SERIAL,
        currency=Currency.USD,
        is_active=True,
        created_at=NOW,
    )
    await world.products.add(product)

    unit = DeviceUnit(
        imei=IMEI(IMEI_A),
        product_id=product.id,
        status=DeviceStatus.IN_STOCK,
        location_id=location,
        acquisition_cost=usd(BOOKED),
        condition=DeviceCondition.USED,
        cash_paid_minor=CASH_PAID_SOM if record_cash else None,
        cash_paid_currency=Currency.UZS if record_cash else None,
        created_at=NOW,
    )
    await world.units.add(unit)

    await world.poster().post(
        Posting(
            document_type=DocumentType.GOODS_RECEIPT,
            document_id=uuid4(),
            entries=[
                PostingEntry(
                    movement_type=MovementType.RECEIPT,
                    product_id=product.id,
                    location_id=location,
                    quantity_delta=1,
                    device_unit_id=unit.id,
                    new_status=DeviceStatus.IN_STOCK,
                    new_location_id=location,
                    money=[MoneyEffect(TransactionType.PURCHASE, -usd(BOOKED))],
                )
            ],
        )
    )
    return world, unit


def reconciler(world) -> LedgerReconciler:
    return LedgerReconciler(
        world.units, world.transaction_queries, world.movement_queries, world.cost_pools()
    )


class TestTheBookedFigureIsWhatCounts:
    async def test_the_purchase_entry_is_exactly_the_dollar_cost(self):
        """FR-3.4c's stated test: booked at $330, and the ledger says −$330
        — not a converted figure, and not the som one."""
        world, _ = await trade_in_store(record_cash=True)

        totals = await world.transaction_queries.totals_by_type()

        assert totals == {(TransactionType.PURCHASE, Currency.USD): usd("-330")}

    async def test_inventory_value_is_the_dollar_cost(self):
        world, _ = await trade_in_store(record_cash=True)

        assert await reconciler(world).on_hand_value() == {Currency.USD: usd("330")}

    async def test_no_figure_anywhere_equals_the_som_amount(self):
        """§4.5b: *"no figure anywhere equals or contains 4 200 000"*."""
        world, _ = await trade_in_store(record_cash=True)

        amounts = [
            *(t.amount.amount_minor for t in world.transactions.rows),
            *(m.amount_minor for m in (await reconciler(world).on_hand_value()).values()),
            *(m.amount_minor for m in (await reconciler(world).ledger_value()).values()),
        ]

        assert all(abs(amount) != CASH_PAID_SOM for amount in amounts)

    async def test_no_som_column_appears_at_all(self):
        """The som figure would otherwise create a UZS total for a store
        that has only ever dealt in dollars — the most visible symptom of
        the leak this guards against."""
        world, _ = await trade_in_store(record_cash=True)

        assert Currency.UZS not in await reconciler(world).on_hand_value()
        assert Currency.UZS not in await reconciler(world).ledger_value()


class TestClearingItChangesNothing:
    """FR-3.4d's method: every figure computed twice, identical both ways."""

    async def test_the_money_ledger_is_identical(self):
        recorded, _ = await trade_in_store(record_cash=True)
        cleared, _ = await trade_in_store(record_cash=False)

        assert (
            await recorded.transaction_queries.totals_by_type()
            == await cleared.transaction_queries.totals_by_type()
        )

    async def test_inventory_value_is_identical(self):
        recorded, _ = await trade_in_store(record_cash=True)
        cleared, _ = await trade_in_store(record_cash=False)

        assert (
            await reconciler(recorded).on_hand_value()
            == await reconciler(cleared).on_hand_value()
        )

    async def test_the_reconciliation_is_identical(self):
        recorded, _ = await trade_in_store(record_cash=True)
        cleared, _ = await trade_in_store(record_cash=False)

        assert await reconciler(recorded).reconcile() == []
        assert await reconciler(cleared).reconcile() == []

    async def test_the_margin_on_a_sale_is_identical(self):
        """Rule 5: margin is same-currency subtraction. A som cost would
        make it uncomputable, which is exactly why the som figure is not
        the cost."""
        margins = []
        for record_cash in (True, False):
            world, unit = await trade_in_store(record_cash=record_cash)
            await world.poster().post(
                Posting(
                    document_type=DocumentType.SALES_INVOICE,
                    document_id=uuid4(),
                    entries=[
                        PostingEntry(
                            movement_type=MovementType.SALE,
                            product_id=unit.product_id,
                            location_id=unit.location_id,
                            quantity_delta=-1,
                            device_unit_id=unit.id,
                            new_status=DeviceStatus.SOLD,
                            new_location_id=None,
                            money=[
                                MoneyEffect(TransactionType.SALE_REVENUE, usd("420")),
                                MoneyEffect(TransactionType.COGS, -unit.acquisition_cost),
                            ],
                        )
                    ],
                )
            )
            totals = await world.transaction_queries.totals_by_type()
            margins.append(
                totals[(TransactionType.SALE_REVENUE, Currency.USD)]
                + totals[(TransactionType.COGS, Currency.USD)]
            )

        assert margins[0] == margins[1] == usd("90")


class TestItIsStillReadableOneRowAtATime:
    """What the field *is* for: the IMEI trace and the unit's own page
    show *"paid 4 200 000 so'm · booked at $330"* months later."""

    async def test_the_unit_reports_what_actually_left_the_till(self):
        _, unit = await trade_in_store(record_cash=True)

        assert unit.cash_paid_display() == "4 200 000 so'm"
        assert unit.acquisition_cost.format() == "$330.00"

    async def test_a_unit_paid_in_its_own_currency_shows_nothing_extra(self):
        _, unit = await trade_in_store(record_cash=False)

        assert unit.cash_paid_display() is None


class TestM8sReportsDoNotSumIt:
    """The failure mode §4.5b names: *"a future report quietly summing
    ``cash_paid``"*. M8 added seven of them, so the guard is stated against
    the payloads they return rather than against the ledger alone.
    """

    def test_no_report_row_has_a_numeric_cash_field(self):
        """``DeviceUnitData`` renders the som as a **string** and every other
        M8 payload has no cash field at all — so there is nothing anywhere
        for a caller to add to a figure."""
        payloads = [
            AgeingRowData,
            NeedsPricingRowData,
            StockOnHandData,
            MovementRowData,
            FinancialLedgerRowData,
            SalesFiguresData,
        ]

        for payload in payloads:
            assert not [
                name for name in payload.model_fields if name.startswith("cash")
            ], payload.__name__

    def test_the_trace_header_carries_it_as_a_string_and_only_that(self):
        assert DeviceUnitData.model_fields["cash_paid"].annotation == str | None
        assert "cash_paid_minor" not in DeviceUnitData.model_fields

    async def test_ageing_reports_the_booked_cost_not_the_som(self):
        """The one M8 row that carries a cost. It is the dollar figure the
        purchase was booked at, never the som that changed hands."""
        _, unit = await trade_in_store(record_cash=True)

        row = AgeingRowData.from_entity(
            AgeingRow(
                device_unit_id=unit.id,
                imei=str(unit.imei),
                product_id=unit.product_id,
                sku="IP11-64",
                product_name="iPhone 11 64GB",
                brand=None,
                condition=unit.condition,
                location_id=unit.location_id,
                location_name="Chilonzor shop",
                created_at=NOW,
                acquisition_cost=unit.acquisition_cost,
                asking_price=usd("420"),
                markdown_count=0,
            ),
            NOW,
            show_cost=True,
        )

        assert row.acquisition_cost.minor == 33000
        assert row.implied_margin.minor == 9000
        assert row.acquisition_cost.currency is Currency.USD
        assert CASH_PAID_SOM not in (
            row.acquisition_cost.minor,
            row.asking_price.minor,
            row.implied_margin.minor,
        )


class TestTheMonthEndReportCannotSeeIt:
    """FR-3.4d's own test, stated in the requirement: run the close over a
    period holding a som-paid trade-in, and every figure matches the same
    close with ``cash_paid`` cleared."""

    async def test_every_figure_is_identical_with_and_without_the_som_record(self):
        recorded, _ = await trade_in_store(record_cash=True)
        cleared, _ = await trade_in_store(record_cash=False)

        with_som = await recorded.month_end_reporter().report(2026, 7)
        without = await cleared.month_end_reporter().report(2026, 7)

        assert with_som.figures == without.figures
        assert with_som.debt == without.debt

    async def test_the_close_grows_no_som_column(self):
        """The most visible symptom of the leak: a UZS inventory figure in
        a store that has only ever dealt in dollars."""
        world, _ = await trade_in_store(record_cash=True)

        july = await world.month_end_reporter().report(2026, 7)

        assert july.figures.closing_inventory.of(Currency.USD) == usd("330")
        assert Currency.UZS not in july.figures.closing_inventory.currencies
        assert Currency.UZS not in july.figures.purchases.currencies
