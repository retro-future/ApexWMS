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
from application.commands.set_exchange_rate import SetExchangeRateCommand
from domain.entities import FinancialTransaction, Location
from domain.enums import (
    AcquisitionSource,
    DeviceCondition,
    DocumentType,
    PaymentType,
    RateKind,
    TrackingType,
    TransactionType,
)
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
from tests.application.test_goods_receipt import confirm as confirm_receipt
from tests.application.test_goods_receipt import opened, scan
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


async def quoted(world: World, at: datetime, rate: str) -> None:
    """A selling rate the store put up on the day *at* falls on."""
    was = world.clock.current
    world.clock.current = at
    await world.set_exchange_rate().handle(
        SetExchangeRateCommand(kind=RateKind.SALE, som_per_usd=rate)
    )
    world.clock.current = was


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


class TestTheSomView:
    """W9 B3: the same month read in som, each figure at the rate of its moment."""

    async def test_a_store_that_never_quoted_a_rate_gets_no_som_view(self):
        world = make_world()
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is None
        # And the per-currency figures are exactly what they always were.
        assert report.figures.revenue.of(Currency.USD) == usd("600")

    async def test_dollars_convert_at_the_rate_of_their_own_day(self):
        world = make_world()
        await quoted(world, MID_JANUARY, "12000")
        await quoted(world, LAST_NIGHT_OF_JANUARY, "12500")
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        # Bought mid-January at 12 000, sold on the 31st at 12 500.
        assert report.som.purchases == som("-4560000")
        assert report.som.revenue == som("7500000")

    async def test_the_latest_rate_is_not_applied_to_the_whole_month(self):
        """The trap this exists to avoid: one rate over a month that moved."""
        world = make_world()
        await quoted(world, MID_JANUARY, "12000")
        await quoted(world, LAST_NIGHT_OF_JANUARY, "12500")
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        assert report.som.purchases != som("-4750000")

    async def test_a_day_before_the_first_quote_takes_the_earliest_rate(self):
        world = make_world()
        await a_bought_and_sold_phone(world, LAST_NIGHT_OF_JANUARY)
        await quoted(world, MID_FEBRUARY, "12500")

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        assert report.som.revenue == som("7500000")
        assert report.som.basis.before_the_first_quote is True

    async def test_a_month_inside_the_log_says_so(self):
        world = make_world()
        await quoted(world, MID_JANUARY, "12000")
        world.clock.current = MID_JANUARY

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        assert report.som.basis.before_the_first_quote is False
        assert str(report.som.basis.opening_rate) == "12000"

    async def test_som_figures_pass_through_untouched(self):
        world = make_world()
        await quoted(world, MID_JANUARY, "12000")
        world.clock.current = MID_JANUARY
        location = a_place(world)
        case = catalogued_full(
            world,
            sku="CASE-BLK",
            price="50000",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 10, som("300000"))

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        # Bought in som already; converting it again would multiply a som
        # figure by a rate.
        assert report.som.purchases == som("-300000")

    async def test_margin_reads_in_som_too(self):
        world = make_world()
        await quoted(world, MID_JANUARY, "12000")
        await a_bought_and_sold_phone(world, MID_JANUARY)

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        assert report.som.margin == som("2640000")
        assert str(report.som.margin_percent) == "36.7"


class TestTheProfitAnOwnerCountsOnPaper:
    """W9 B7: the gap between the converted figures and the real money.

    A store buys a handset off a walk-in for som and sells it for som. The
    owner's arithmetic is one subtraction. Until the rate gain existed, the
    report could not reach that number from either side: the books value
    the handset in dollars, and the two conversions swallow the spread the
    store actually earned.
    """

    async def test_it_matches_the_money_in_less_the_money_out(self):
        world = make_world()
        await quoted(world, MID_JANUARY, "12500")
        world.clock.current = MID_JANUARY

        # Bought off a walk-in: valued at $330, 3 600 000 som handed over.
        receipt, product, location = await opened(
            world, source=AcquisitionSource.TRADE_IN
        )
        await scan(
            world,
            receipt,
            condition=DeviceCondition.USED,
            acquisition_cost="330",
            asking_price="600",
            cash_paid="3600000",
            cash_paid_currency=Currency.UZS,
        )
        await confirm_receipt(world, receipt)

        # Sold the same day for $600, settled with 7 620 000 som.
        invoice = await a_scanned_invoice(world, location, a_customer(world))
        assert invoice is not None
        await world.confirm_sales_invoice().handle(
            ConfirmSalesInvoiceCommand(sales_invoice_id=invoice.id)
        )
        await world.record_payment().handle(
            RecordPaymentCommand(sales_invoice_id=invoice.id, amount="7620000")
        )

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        # 4 125 000 - 3 600 000 on the buy, 7 620 000 - 7 500 000 on the sale.
        assert report.som.rate_gain == som("645000")
        assert report.som.margin == som("3375000")
        # And the one number: 7 620 000 taken, 3 600 000 paid out.
        assert report.som.profit == som("4020000")

    async def test_a_sale_nobody_settled_is_left_out_rather_than_counted_lost(self):
        world = make_world()
        await quoted(world, MID_JANUARY, "12500")
        await a_bought_and_sold_phone(world, MID_JANUARY)

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        assert report.som.rate_gain == som("0")

    async def test_the_markup_on_a_debt_is_its_own_line(self):
        """W9 B4: the seller named 7 800 000 on a phone worth 7 500 000 at
        the day's rate. No rate was applied to reach it, so the 300 000 is
        what the shop earns for waiting, not a rate gain."""
        world = make_world()
        await quoted(world, MID_JANUARY, "12500")
        world.clock.current = MID_JANUARY
        await a_credit_sale(world)

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        assert report.som.instalment_income == som("300000")
        assert report.som.rate_gain == som("0")

    async def test_a_payment_on_a_debt_is_not_counted_a_second_time(self):
        """The 800 000 down payment is that debt arriving, not more money.
        Counting both would read 1 100 000 where the shop earned 300 000."""
        world = make_world()
        await quoted(world, MID_JANUARY, "12500")
        world.clock.current = MID_JANUARY
        sale_id = await a_credit_sale(world)
        await world.record_payment().handle(
            RecordPaymentCommand(sales_invoice_id=sale_id, amount="1000000")
        )

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        assert report.som.instalment_income == som("300000")


class TestARateChangedDuringTheDay:
    """The store moved its rate twice in one morning. Every figure reads at
    the quote in force at its own moment, never at the day's last one."""

    async def test_a_trade_in_before_the_correction_reads_at_the_earlier_quote(self):
        """The case found on the server: bought at 12 000 while 12 500 was
        quoted, then the rate went down to 11 850. The deal earned money."""
        world = make_world()
        await quoted(world, MID_JANUARY, "12500")
        await quoted(world, MID_JANUARY + timedelta(minutes=40), "11850")
        world.clock.current = MID_JANUARY + timedelta(minutes=5)
        receipt, _, _ = await opened(world, source=AcquisitionSource.TRADE_IN)
        await scan(
            world,
            receipt,
            condition=DeviceCondition.USED,
            acquisition_cost="400",
            asking_price="450",
            cash_paid="4800000",
            cash_paid_currency=Currency.UZS,
        )
        await confirm_receipt(world, receipt)

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        # $400 at 12 500 is 5 000 000; 4 800 000 was handed over.
        assert report.som.rate_gain == som("200000")
        assert report.som.purchases == som("-5000000")

    async def test_a_trade_in_after_the_correction_reads_at_the_correction(self):
        world = make_world()
        await quoted(world, MID_JANUARY, "12500")
        await quoted(world, MID_JANUARY + timedelta(minutes=40), "11850")
        world.clock.current = MID_JANUARY + timedelta(minutes=45)
        receipt, _, _ = await opened(world, source=AcquisitionSource.TRADE_IN)
        await scan(
            world,
            receipt,
            condition=DeviceCondition.USED,
            acquisition_cost="400",
            asking_price="450",
            cash_paid="4800000",
            cash_paid_currency=Currency.UZS,
        )
        await confirm_receipt(world, receipt)

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        assert report.som.rate_gain == som("-60000")

    async def test_a_credit_sale_before_the_correction_reads_at_the_earlier_quote(self):
        world = make_world()
        await quoted(world, MID_JANUARY - timedelta(hours=1), "12500")
        await quoted(world, MID_JANUARY + timedelta(hours=1), "13500")
        await a_credit_sale(world)

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        # $600 at 12 500 is 7 500 000; the seller named 7 800 000. Read at
        # the later 13 500 it would have been a 300 000 loss.
        assert report.som.instalment_income == som("300000")

    async def test_revenue_reads_at_the_quote_in_force_when_it_was_sold(self):
        world = make_world()
        await quoted(world, MID_JANUARY, "12000")
        await quoted(world, MID_JANUARY + timedelta(hours=2), "13000")
        await a_bought_and_sold_phone(world, MID_JANUARY + timedelta(hours=1))

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        assert report.som.revenue == som("7200000")
        assert report.som.cost_of_goods == som("-4560000")

    async def test_the_basis_names_the_quote_in_force_at_each_end(self):
        world = make_world()
        await quoted(world, MID_JANUARY, "12000")
        await quoted(world, LAST_NIGHT_OF_JANUARY - timedelta(hours=2), "12400")
        await quoted(world, LAST_NIGHT_OF_JANUARY, "12500")
        world.clock.current = MID_JANUARY

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        assert str(report.som.basis.opening_rate) == "12000"
        assert str(report.som.basis.closing_rate) == "12500"

    async def test_a_sale_before_the_days_first_quote_reads_at_yesterdays(self):
        world = make_world()
        await quoted(world, MID_JANUARY - timedelta(days=1), "12000")
        await quoted(world, MID_JANUARY + timedelta(hours=1), "13000")
        await a_bought_and_sold_phone(world, MID_JANUARY)

        report = await world.month_end_reporter().report(2026, 1)

        assert report.som is not None
        assert report.som.revenue == som("7200000")


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
