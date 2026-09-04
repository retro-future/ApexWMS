"""The month-end close through the reporter — PRD §5.10, FR-10.4 to FR-10.10.

Two things here cannot be checked anywhere else. **Period boundaries run in
the tenant's timezone** (FR-10.8), so a sale at 23:30 on the 31st in
Tashkent has to land in that month and not the next one — the world's
default store is on ``Asia/Tashkent``, five hours ahead, which is exactly
the offset that makes the bug appear. And **the debt movement has to add
up**: opening plus what was booked, less what was collected and what a
cancellation voided, is the closing balance or the report is wrong about
somebody's money.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from application.commands.cancel_sales_invoice import CancelSalesInvoiceCommand
from application.commands.confirm_sales_invoice import ConfirmSalesInvoiceCommand
from application.commands.record_payment import RecordPaymentCommand
from domain.entities import FinancialTransaction, Location
from domain.enums import DocumentType, PaymentType, TrackingType, TransactionType
from domain.value_objects import Currency, Money
from tests.application.builders import World, make_world
from tests.application.test_credit_sales import (
    a_customer,
    a_place,
    a_scanned_invoice,
    catalogued,
    in_stock,
    som,
    usd,
)
from tests.application.test_sales_invoice import (
    CASE_BARCODE,
    stocked_accessory,
)
from tests.application.test_sales_invoice import catalogued as catalogued_full

# Tashkent is UTC+5, so January 2026 runs [2025-12-31 19:00Z, 2026-01-31 19:00Z).
LAST_NIGHT_OF_JANUARY = datetime(2026, 1, 31, 18, 30, tzinfo=UTC)
MID_JANUARY = datetime(2026, 1, 15, 9, 0, tzinfo=UTC)
MID_FEBRUARY = datetime(2026, 2, 15, 9, 0, tzinfo=UTC)
MID_MARCH = datetime(2026, 3, 15, 9, 0, tzinfo=UTC)


async def a_bought_and_sold_phone(world: World, sold_at: datetime) -> Location:
    """One $600 phone received mid-January and sold at *sold_at*."""
    location = a_place(world)
    product = catalogued(world)
    customer = a_customer(world)

    world.clock.current = MID_JANUARY
    await in_stock(world, product, location)

    world.clock.current = sold_at
    invoice = await a_scanned_invoice(world, location, customer)
    assert invoice is not None
    await world.confirm_sales_invoice().handle(
        ConfirmSalesInvoiceCommand(sales_invoice_id=invoice.id)
    )
    return location


async def a_credit_sale(world: World, location: Location | None = None) -> UUID:
    """The FR-11.5 example, sold in January: a $600 phone for 7 800 000
    so'm with an 800 000 down payment."""
    location = location or a_place(world)
    product = catalogued(world)
    customer = a_customer(world)

    world.clock.current = MID_JANUARY
    await in_stock(world, product, location)
    invoice = await a_scanned_invoice(world, location, customer)
    assert invoice is not None
    result = await world.confirm_sales_invoice().handle(
        ConfirmSalesInvoiceCommand(
            sales_invoice_id=invoice.id,
            payment_type=PaymentType.STORE_CREDIT,
            debt="7800000",
            down_payment="800000",
        )
    )
    assert result.data is not None
    return result.data.id


class TestPeriodBoundariesRunInTheTenantTimezone:
    """FR-10.8. Without this the store's last sale of the month is booked
    into the next one, and both months are quietly wrong."""

    async def test_a_sale_at_2330_on_the_31st_lands_in_that_month(self):
        world = make_world()
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)

        january = await world.month_end_reporter().report(2026, 1)

        assert january.figures.revenue.of(Currency.USD) == usd("600")

    async def test_and_not_in_the_next_one(self):
        world = make_world()
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)

        february = await world.month_end_reporter().report(2026, 2)

        assert february.figures.revenue.of(Currency.USD) == usd("0")

    async def test_an_hour_later_it_is_february(self):
        """00:30 local on the 1st — the same UTC evening, the other month."""
        world = make_world()
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY + timedelta(hours=1))

        january = await world.month_end_reporter().report(2026, 1)
        february = await world.month_end_reporter().report(2026, 2)

        assert january.figures.revenue.of(Currency.USD) == usd("0")
        assert february.figures.revenue.of(Currency.USD) == usd("600")

    async def test_the_period_carries_the_zone_it_was_computed_in(self):
        world = make_world()

        period = (await world.month_end_reporter().report(2026, 1)).period

        assert period.timezone == "Asia/Tashkent"
        assert period.start == datetime(2025, 12, 31, 19, 0, tzinfo=UTC)
        assert period.end == datetime(2026, 1, 31, 19, 0, tzinfo=UTC)

    async def test_december_rolls_into_the_next_year(self):
        world = make_world()

        period = (await world.month_end_reporter().report(2026, 12)).period

        assert period.end == datetime(2026, 12, 31, 19, 0, tzinfo=UTC)


class TestTheAccrualView:
    async def test_a_phone_bought_and_sold_in_one_month(self):
        world = make_world()
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)

        figures = (await world.month_end_reporter().report(2026, 1)).figures

        assert figures.purchases.of(Currency.USD) == usd("-380")
        assert figures.cost_of_goods.of(Currency.USD) == usd("-380")
        assert figures.revenue.of(Currency.USD) == usd("600")

    async def test_margin_is_revenue_plus_cost_with_no_sign_flipped(self):
        world = make_world()
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)

        figures = (await world.month_end_reporter().report(2026, 1)).figures

        assert figures.margin[Currency.USD] == usd("220")
        assert str(figures.margin_percent[Currency.USD]) == "36.7"

    async def test_a_month_that_sold_nothing_has_no_margin_percentage(self):
        """Not 0.0 — that would read as a month that broke even."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        world.clock.current = MID_JANUARY
        await in_stock(world, product, location)

        figures = (await world.month_end_reporter().report(2026, 1)).figures

        assert figures.margin_percent.get(Currency.USD) is None

    async def test_february_opens_on_what_january_closed_with(self):
        """FR-10.5's first line, and §5.10's "opening = previous closing":
        both roll forward from the same immutable ledger, so this is exact
        rather than nearly right."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        world.clock.current = MID_JANUARY
        await in_stock(world, product, location)

        january = await world.month_end_reporter().report(2026, 1)
        february = await world.month_end_reporter().report(2026, 2)

        assert january.figures.closing_inventory.of(Currency.USD) == usd("380")
        assert february.figures.opening_inventory.of(Currency.USD) == usd("380")

    async def test_the_unsold_phone_is_still_on_the_shelf_at_period_end(self):
        """FR-10.6: the closing figure broken down by where it sits."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        world.clock.current = MID_JANUARY
        await in_stock(world, product, location)

        january = await world.month_end_reporter().report(2026, 1)

        assert [entry.location_id for entry in january.closing_by_location] == [
            location.id
        ]
        assert january.closing_by_location[0].value.of(Currency.USD) == usd("380")

    async def test_an_accessory_on_the_shelf_keeps_its_location_name(self):
        """FR-10.6: a quantity accessory's closing value is attributed to a
        named location, not left unattributed — moved_pairs carries no name."""
        world = make_world()
        location = a_place(world)
        case = catalogued_full(
            world,
            sku="CASE-BLK",
            price="50000",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            barcode=CASE_BARCODE,
        )
        world.clock.current = MID_JANUARY
        await stocked_accessory(world, case, location, 3, som("90000"))

        january = await world.month_end_reporter().report(2026, 1)

        assert [e.location_id for e in january.closing_by_location] == [location.id]
        assert january.closing_by_location[0].location_name == location.name

    async def test_a_phone_sold_before_period_end_is_off_the_shelf(self):
        world = make_world()
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)

        january = await world.month_end_reporter().report(2026, 1)

        assert january.closing_by_location == []
        assert january.figures.closing_inventory.of(Currency.USD) == usd("0")


class TestClosingValueReconciles:
    """FR-10.7: the money ledger's closing figure against what the goods say."""

    async def test_a_clean_store_reconciles(self):
        world = make_world()
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)

        january = await world.month_end_reporter().report(2026, 1)

        assert january.reconciles
        assert january.discrepancies == []

    async def test_a_purchase_with_no_goods_behind_it_is_surfaced(self):
        """The mismatch is reported beside the figures, never folded into
        them — rewriting one to match the other destroys the evidence of
        whatever wrote it wrong."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        world.clock.current = MID_JANUARY
        await in_stock(world, product, location)
        world.transactions.rows.append(
            FinancialTransaction(
                occurred_at=MID_JANUARY,
                txn_type=TransactionType.PURCHASE,
                amount=usd("-100"),
                product_id=product.id,
                location_id=location.id,
                document_type=DocumentType.GOODS_RECEIPT,
                document_id=uuid4(),
                user_id=uuid4(),
            )
        )

        january = await world.month_end_reporter().report(2026, 1)

        assert not january.reconciles
        subjects = [found.subject for found in january.discrepancies]
        assert "closing inventory value in USD" in subjects
        assert january.figures.closing_inventory.of(Currency.USD) == usd("480")


class TestTheDebtAndCashView:
    """§4.7 and FR-10.5's last two lines. Always som, never a pair."""

    async def test_a_credit_sale_opens_the_debt_and_records_the_down_payment(self):
        world = make_world()
        await a_credit_sale(world)

        january = await world.month_end_reporter().report(2026, 1)

        assert january.debt.opening == som("0")
        assert january.debt.booked == som("7800000")
        assert january.debt.collected == som("800000")
        assert january.debt.closing == som("7000000")

    async def test_the_next_month_opens_on_the_balance_the_last_one_closed_with(self):
        world = make_world()
        invoice_id = await a_credit_sale(world)
        world.clock.current = MID_FEBRUARY
        await world.record_payment().handle(
            RecordPaymentCommand(sales_invoice_id=invoice_id, amount="2000000")
        )

        february = await world.month_end_reporter().report(2026, 2)

        assert february.debt.opening == som("7000000")
        assert february.debt.collected == som("2000000")
        assert february.debt.closing == som("5000000")

    async def test_a_cancellation_voids_the_remaining_debt(self):
        """FR-11.11: the movement has to absorb a void, or opening plus
        booked less collected simply does not reach closing."""
        world = make_world()
        invoice_id = await a_credit_sale(world)
        world.clock.current = MID_FEBRUARY
        await world.record_payment().handle(
            RecordPaymentCommand(sales_invoice_id=invoice_id, amount="2000000")
        )
        world.clock.current = MID_MARCH
        await world.cancel_sales_invoice().handle(
            CancelSalesInvoiceCommand(sales_invoice_id=invoice_id, reason="returned")
        )

        march = await world.month_end_reporter().report(2026, 3)

        assert march.debt.opening == som("5000000")
        assert march.debt.voided == som("5000000")
        assert march.debt.closing == som("0")

    async def test_the_movement_adds_up_in_every_month(self):
        world = make_world()
        invoice_id = await a_credit_sale(world)
        world.clock.current = MID_FEBRUARY
        await world.record_payment().handle(
            RecordPaymentCommand(sales_invoice_id=invoice_id, amount="2000000")
        )
        world.clock.current = MID_MARCH
        await world.cancel_sales_invoice().handle(
            CancelSalesInvoiceCommand(sales_invoice_id=invoice_id, reason="returned")
        )

        for month in (1, 2, 3):
            debt = (await world.month_end_reporter().report(2026, month)).debt
            rolled = debt.opening + debt.booked - debt.collected - debt.voided
            assert rolled == debt.closing, f"month {month} does not add up"

    async def test_cash_collected_is_not_revenue(self):
        """FR-11.7 from the report side: the som that came in and the
        dollars that were earned are different figures in different
        columns."""
        world = make_world()
        await a_credit_sale(world)

        january = await world.month_end_reporter().report(2026, 1)

        assert january.debt.collected == som("800000")
        assert january.figures.revenue.of(Currency.USD) == usd("600")
        assert january.figures.revenue.of(Currency.UZS) == som("0")


class TestSalesByFinancingType:
    async def test_a_store_credit_sale_is_labelled_as_one(self):
        world = make_world()
        await a_credit_sale(world)

        january = await world.month_end_reporter().report(2026, 1)

        assert [(row.payment_type, row.invoice_count) for row in january.financing] == [
            (PaymentType.STORE_CREDIT, 1)
        ]
        assert january.financing[0].revenue == usd("600")

    async def test_a_cash_sale_is_labelled_as_one(self):
        world = make_world()
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)

        january = await world.month_end_reporter().report(2026, 1)

        assert [row.payment_type for row in january.financing] == [
            PaymentType.PAID_IN_FULL
        ]

    async def test_the_split_adds_back_up_to_the_reports_own_revenue(self):
        world = make_world()
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)

        january = await world.month_end_reporter().report(2026, 1)

        split = Money.zero(Currency.USD)
        for row in january.financing:
            split = split + row.revenue
        assert split == january.figures.revenue.of(Currency.USD)


class TestRerunningAPastMonthIsIdentical:
    """FR-10.10. Reproducibility here is structural — no figure is ever
    converted, so there is no rate that could have moved between runs."""

    async def test_the_same_month_twice_gives_the_same_figures(self):
        world = make_world()
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)

        first = await world.month_end_reporter().report(2026, 1)
        world.clock.current = MID_MARCH
        second = await world.month_end_reporter().report(2026, 1)

        assert first.figures == second.figures
        assert first.debt == second.debt
        assert first.closing_by_location == second.closing_by_location


class TestScopingToOneLocation:
    async def test_a_location_filter_narrows_the_accrual_figures(self):
        world = make_world()
        location = await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)
        elsewhere = a_warehouse(world)

        at_shop = await world.month_end_reporter().report(2026, 1, location.id)
        at_warehouse = await world.month_end_reporter().report(2026, 1, elsewhere.id)

        assert at_shop.figures.revenue.of(Currency.USD) == usd("600")
        assert at_warehouse.figures.revenue.of(Currency.USD) == usd("0")

    async def test_debt_stays_store_wide(self):
        """Debt belongs to a customer, not a shelf, and a payment records no
        location at all — narrowing it would invent a figure."""
        world = make_world()
        await a_credit_sale(world)
        elsewhere = a_warehouse(world)

        at_warehouse = await world.month_end_reporter().report(2026, 1, elsewhere.id)

        assert at_warehouse.debt.closing == som("7000000")


def a_warehouse(world: World) -> Location:
    location = Location(name="Warehouse", is_active=True, created_at=world.clock.now())
    world.locations.by_id[location.id] = location
    return location
