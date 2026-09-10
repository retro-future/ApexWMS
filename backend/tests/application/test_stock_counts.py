"""Counting the shelf end to end through the handlers — PRD §5.6.

No database: the whole flow runs against the in-memory fakes. What these
cover that the domain tests cannot is everything needing a lookup — the
opening snapshot, what an adjustment is worth, and what confirming does to
a handset the store had never heard of.

``TestHideAPhoneAndRunACount`` is the milestone's demo, written down as a
test: hide a phone, count, watch the system find it missing and book the
loss (§10, M6).
"""


import pytest

from application.commands.cancel_stock_count import CancelStockCountCommand
from application.commands.close_stock_count import CloseStockCountCommand
from application.commands.confirm_sales_invoice import ConfirmSalesInvoiceCommand
from application.commands.confirm_stock_count import ConfirmStockCountCommand
from application.commands.count_stock_count_line import CountStockCountLineCommand
from application.commands.create_sales_invoice import CreateSalesInvoiceCommand
from application.commands.open_stock_count import OpenStockCountCommand
from application.commands.scan_invoice_line import ScanInvoiceLineCommand
from application.commands.scan_stock_count_unit import ScanStockCountUnitCommand
from application.commands.unscan_stock_count_unit import UnscanStockCountUnitCommand
from application.queries.list_stock_counts import ListStockCountsQuery
from application.services import LedgerReconciler
from application.specs import DeviceUnitByImei, StockLevelForPair
from domain.enums import (
    CountOutcome,
    DeviceCondition,
    DeviceStatus,
    DocumentType,
    MovementType,
    TrackingType,
    TransactionType,
)
from domain.errors import (
    CountAlreadyClosedError,
    CountNotClosedError,
    PriceNotSetError,
    UnpricedUnitError,
)
from domain.permissions import Permission
from domain.services import PriceResolver
from domain.value_objects import Currency
from tests.application.builders import World, make_world
from tests.application.test_sales_invoice import (
    CASE_BARCODE,
    OTHER_IMEI,
    PHONE_IMEI,
    a_place,
    catalogued,
    in_stock,
    stocked_accessory,
    usd,
    uzs,
)

# A third handset the store has never heard of — FR-6.4b's surprise.
UNKNOWN_IMEI = "358240051111110"


async def opened_count(world: World, location, **overrides):
    result = await world.open_stock_count().handle(
        OpenStockCountCommand(location_id=location.id, **overrides)
    )
    assert result.data is not None
    count = await world.counts.get(result.data.id)
    assert count is not None
    return count


async def scan(world: World, count, code: str, **body):
    return await world.scan_stock_count_unit().handle(
        ScanStockCountUnitCommand(code=code, stock_count_id=count.id, **body)
    )


async def close_and_confirm(world: World, count, actor=None):
    await world.close_stock_count(actor).handle(
        CloseStockCountCommand(stock_count_id=count.id)
    )
    return await world.confirm_stock_count(actor).handle(
        ConfirmStockCountCommand(stock_count_id=count.id)
    )


def adjustments(world: World, count):
    return [
        m
        for m in world.movements.rows
        if m.document_type is DocumentType.STOCK_COUNT and m.document_id == count.id
    ]


def money(world: World, count):
    return [
        t
        for t in world.transactions.rows
        if t.document_type is DocumentType.STOCK_COUNT and t.document_id == count.id
    ]


class TestTheSnapshotIsTakenWhenTheCountOpens:
    """FR-6.1: a count takes hours, and the books keep moving underneath it."""

    async def test_every_handset_here_gets_a_row(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location, imei=PHONE_IMEI)
        await in_stock(world, product, location, imei=OTHER_IMEI)

        count = await opened_count(world, location)

        assert {str(u.imei) for u in count.units} == {PHONE_IMEI, OTHER_IMEI}
        assert all(u.expected and not u.scanned for u in count.units)

    async def test_handsets_at_another_location_are_not_counted(self):
        world = make_world()
        here = a_place(world, "Shop")
        there = a_place(world, "Stockroom")
        product = catalogued(world)
        await in_stock(world, product, here, imei=PHONE_IMEI)
        await in_stock(world, product, there, imei=OTHER_IMEI)

        count = await opened_count(world, here)

        assert [str(u.imei) for u in count.units] == [PHONE_IMEI]

    async def test_every_accessory_level_gets_a_line(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="50000",
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 10, uzs("300000"))

        count = await opened_count(world, location)

        assert [line.expected_quantity for line in count.lines] == [10]
        assert count.lines[0].counted_quantity is None

    async def test_a_sale_during_the_count_does_not_change_what_was_expected(self):
        """The reason the snapshot is taken at open: recomputing at close
        would report a phone sold mid-count as missing and book a loss on
        stock the store had just been paid for."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        unit = await in_stock(world, product, location)
        count = await opened_count(world, location)

        unit.status = DeviceStatus.SOLD
        unit.location_id = None

        assert [str(u.imei) for u in count.units] == [PHONE_IMEI]


class TestHideAPhoneAndRunACount:
    """M6's demo (§10): the missing handset is found and the loss booked."""

    async def test_the_unscanned_handset_reports_as_missing(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location, imei=PHONE_IMEI)
        await in_stock(world, product, location, imei=OTHER_IMEI)
        count = await opened_count(world, location)

        await scan(world, count, PHONE_IMEI)
        result = await world.close_stock_count().handle(
            CloseStockCountCommand(stock_count_id=count.id)
        )

        assert result.data is not None
        assert result.data.matched_count == 1
        assert result.data.missing_count == 1
        assert result.data.unexpected_count == 0

    async def test_confirming_writes_the_handset_off(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        hidden = await in_stock(world, product, location, imei=PHONE_IMEI, cost="380")
        count = await opened_count(world, location)

        await close_and_confirm(world, count)

        gone = await world.units.get(hidden.id)
        assert gone is not None
        assert gone.status is DeviceStatus.WRITTEN_OFF
        assert gone.location_id is None

    async def test_the_loss_is_booked_as_a_count_adjustment_and_not_a_write_off(self):
        """§4.6: "we looked and it was gone" and "we know it was stolen" are
        different claims, and §5.10 reports them in different columns."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location, cost="380")
        count = await opened_count(world, location)

        await close_and_confirm(world, count)

        booked = money(world, count)
        assert [t.txn_type for t in booked] == [TransactionType.COUNT_ADJUSTMENT]
        assert booked[0].amount == -usd("380")
        assert TransactionType.WRITE_OFF_LOSS not in {
            t.txn_type for t in world.transactions.rows
        }

    async def test_the_movement_is_one_negative_count_adjustment(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        count = await opened_count(world, location)

        await close_and_confirm(world, count)

        moves = adjustments(world, count)
        assert [m.movement_type for m in moves] == [MovementType.COUNT_ADJUSTMENT]
        assert [m.quantity_delta for m in moves] == [-1]

    async def test_a_handset_sold_while_the_count_was_open_is_not_a_loss(self):
        """The snapshot froze what the books said hours ago. A phone sold
        since is not missing, it is sold — and the ledger already accounts
        for it, so writing it off again would take its cost out twice."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        unit = await in_stock(world, product, location, cost="380")
        count = await opened_count(world, location)

        invoice = await world.create_sales_invoice().handle(
            CreateSalesInvoiceCommand(location_id=location.id)
        )
        assert invoice.data is not None
        await world.scan_invoice_line().handle(
            ScanInvoiceLineCommand(code=PHONE_IMEI, sales_invoice_id=invoice.data.id)
        )
        await world.confirm_sales_invoice().handle(
            ConfirmSalesInvoiceCommand(sales_invoice_id=invoice.data.id)
        )

        await close_and_confirm(world, count)

        assert adjustments(world, count) == []
        assert money(world, count) == []
        sold = await world.units.get(unit.id)
        assert sold is not None
        assert sold.status is DeviceStatus.SOLD

    async def test_and_the_ledgers_still_reconcile_after_that(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        await in_stock(world, product, location, cost="380")
        count = await opened_count(world, location)

        invoice = await world.create_sales_invoice().handle(
            CreateSalesInvoiceCommand(location_id=location.id)
        )
        assert invoice.data is not None
        await world.scan_invoice_line().handle(
            ScanInvoiceLineCommand(code=PHONE_IMEI, sales_invoice_id=invoice.data.id)
        )
        await world.confirm_sales_invoice().handle(
            ConfirmSalesInvoiceCommand(sales_invoice_id=invoice.data.id)
        )
        await close_and_confirm(world, count)

        reconciler = LedgerReconciler(
            world.units, world.transaction_queries, world.movement_queries, world.cost_pools()
        )

        assert await reconciler.reconcile() == []

    async def test_a_matched_handset_writes_nothing_at_all(self):
        """The books were right. A movement of zero would be a row asserting
        that something happened."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        count = await opened_count(world, location)
        await scan(world, count, PHONE_IMEI)

        await close_and_confirm(world, count)

        assert adjustments(world, count) == []
        assert money(world, count) == []


class TestASurpriseHandset:
    """FR-6.4b: an IMEI the store has never seen, found on the shelf."""

    async def test_it_is_accepted_rather_than_refused(self):
        """A count that rejected the very thing it exists to find would be
        useless."""
        world = make_world()
        location = a_place(world)
        catalogued(world)
        count = await opened_count(world, location)

        result = await scan(world, count, UNKNOWN_IMEI)

        assert result.data is not None
        assert result.data.unit is not None
        assert result.data.unit.outcome is CountOutcome.UNEXPECTED
        assert result.data.unit.is_surprise is True

    async def test_confirming_without_a_cost_is_refused(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        count = await opened_count(world, location)
        await scan(world, count, UNKNOWN_IMEI, product_id=product.id)
        await world.close_stock_count().handle(
            CloseStockCountCommand(stock_count_id=count.id)
        )

        with pytest.raises(UnpricedUnitError, match=UNKNOWN_IMEI):
            await world.confirm_stock_count().handle(
                ConfirmStockCountCommand(stock_count_id=count.id)
            )

    async def test_confirming_creates_the_handset_in_stock(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        count = await opened_count(world, location)
        await scan(world, count, UNKNOWN_IMEI, product_id=product.id, acquisition_cost="300")

        await close_and_confirm(world, count)

        created = await world.units.find_one(DeviceUnitByImei(UNKNOWN_IMEI))
        assert created is not None
        assert created.status is DeviceStatus.IN_STOCK
        assert created.location_id == location.id
        assert created.acquisition_cost == usd("300")

    async def test_it_enters_used_and_with_no_asking_price(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        count = await opened_count(world, location)
        await scan(world, count, UNKNOWN_IMEI, product_id=product.id, acquisition_cost="300")

        await close_and_confirm(world, count)

        created = await world.units.find_one(DeviceUnitByImei(UNKNOWN_IMEI))
        assert created is not None
        assert created.asking_price is None
        assert created.condition is DeviceCondition.USED

    async def test_and_therefore_cannot_be_sold_until_somebody_prices_it(self):
        """FR-6.4b's own test: refused for want of a price, **not** quoted
        the catalog's new-goods figure."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        count = await opened_count(world, location)
        await scan(world, count, UNKNOWN_IMEI, product_id=product.id, acquisition_cost="300")
        await close_and_confirm(world, count)

        created = await world.units.find_one(DeviceUnitByImei(UNKNOWN_IMEI))
        assert created is not None
        with pytest.raises(PriceNotSetError):
            PriceResolver.resolve(created, product)

    async def test_the_surplus_is_booked_positive_at_the_stated_cost(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        count = await opened_count(world, location)
        await scan(world, count, UNKNOWN_IMEI, product_id=product.id, acquisition_cost="300")

        await close_and_confirm(world, count)

        booked = money(world, count)
        assert [t.txn_type for t in booked] == [TransactionType.COUNT_ADJUSTMENT]
        assert booked[0].amount == usd("300")
        assert [m.quantity_delta for m in adjustments(world, count)] == [1]

    async def test_it_names_the_count_it_came_from(self):
        """The IMEI trace has to be able to say where the handset came from,
        and it did not come through a receipt."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        count = await opened_count(world, location)
        await scan(world, count, UNKNOWN_IMEI, product_id=product.id, acquisition_cost="300")

        await close_and_confirm(world, count)

        created = await world.units.find_one(DeviceUnitByImei(UNKNOWN_IMEI))
        assert created is not None
        assert created.source_document_type is DocumentType.STOCK_COUNT
        assert created.source_document_id == count.id

    async def test_a_cost_may_be_supplied_after_the_scan(self):
        """The storekeeper holding the phone may hold neither the answer nor
        the pricing permission."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        count = await opened_count(world, location)
        await scan(world, count, UNKNOWN_IMEI)

        await scan(world, count, UNKNOWN_IMEI, product_id=product.id, acquisition_cost="300")
        await close_and_confirm(world, count)

        created = await world.units.find_one(DeviceUnitByImei(UNKNOWN_IMEI))
        assert created is not None
        assert created.acquisition_cost == usd("300")

    async def test_a_cost_may_also_be_supplied_after_closing(self):
        """The worklist that reports a surprise appears only after close —
        pricing it there has to work, not just before (FR-6.4b)."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        count = await opened_count(world, location)
        await scan(world, count, UNKNOWN_IMEI, product_id=product.id)
        await world.close_stock_count().handle(
            CloseStockCountCommand(stock_count_id=count.id)
        )

        result = await scan(world, count, UNKNOWN_IMEI, acquisition_cost="300")
        assert result.data is not None

        priced = await world.counts.get(count.id)
        assert priced is not None
        row = next(u for u in priced.units if str(u.imei) == UNKNOWN_IMEI)
        assert row.acquisition_cost == usd("300")

        confirmed = await world.confirm_stock_count().handle(
            ConfirmStockCountCommand(stock_count_id=count.id)
        )
        assert confirmed.data is not None

    async def test_a_closed_count_still_refuses_a_genuinely_new_imei(self):
        """Pricing a known surprise is allowed after close; discovering a
        handset the count never scanned is a different report entirely."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        count = await opened_count(world, location)
        await world.close_stock_count().handle(
            CloseStockCountCommand(stock_count_id=count.id)
        )

        with pytest.raises(CountAlreadyClosedError):
            await scan(world, count, UNKNOWN_IMEI)


class TestAHandsetFoundWhereItWasNotExpected:
    """Known to the store, just not here. It keeps the cost it was bought at."""

    async def test_it_is_unexpected_but_not_a_surprise(self):
        world = make_world()
        here = a_place(world, "Shop")
        there = a_place(world, "Stockroom")
        product = catalogued(world)
        await in_stock(world, product, there, imei=PHONE_IMEI)
        count = await opened_count(world, here)

        result = await scan(world, count, PHONE_IMEI)

        assert result.data is not None
        assert result.data.unit is not None
        assert result.data.unit.outcome is CountOutcome.UNEXPECTED
        assert result.data.unit.is_surprise is False

    async def test_the_goods_move_and_the_money_does_not(self):
        """The store already owns it and already booked what it paid, so
        this is a location correction, not a change in value."""
        world = make_world()
        here = a_place(world, "Shop")
        there = a_place(world, "Stockroom")
        product = catalogued(world)
        unit = await in_stock(world, product, there, imei=PHONE_IMEI, cost="380")
        count = await opened_count(world, here)
        await scan(world, count, PHONE_IMEI)

        await close_and_confirm(world, count)

        assert [m.quantity_delta for m in adjustments(world, count)] == [1]
        assert money(world, count) == []
        assert unit.location_id == here.id

    async def test_and_the_ledgers_still_reconcile(self):
        """Booking its cost a second time would report inventory worth
        double the shelves, and this is the check that says so (FR-10.7)."""
        world = make_world()
        here = a_place(world, "Shop")
        there = a_place(world, "Stockroom")
        product = catalogued(world)
        await in_stock(world, product, there, imei=PHONE_IMEI, cost="380")
        count = await opened_count(world, here)
        await scan(world, count, PHONE_IMEI)
        await close_and_confirm(world, count)

        reconciler = LedgerReconciler(
            world.units, world.transaction_queries, world.movement_queries, world.cost_pools()
        )

        assert await reconciler.reconcile() == []
        assert (await reconciler.on_hand_value())[Currency.USD] == usd("380")

    async def test_a_handset_the_books_wrote_off_does_book_its_value(self):
        """The other side of the same rule: this one really is entering
        inventory, so on-hand value gains its cost and the ledger must too."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        lost = await in_stock(world, product, location, cost="380")

        first = await opened_count(world, location)
        await close_and_confirm(world, first)
        assert lost.status is DeviceStatus.WRITTEN_OFF

        second = await opened_count(world, location)
        await scan(world, second, PHONE_IMEI)
        await close_and_confirm(world, second)

        assert money(world, second)[0].amount == usd("380")
        reconciler = LedgerReconciler(
            world.units, world.transaction_queries, world.movement_queries, world.cost_pools()
        )
        assert await reconciler.reconcile() == []


class TestCountingAccessories:
    async def test_a_typed_count_adjusts_the_difference(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="50000",
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 10, uzs("300000"))
        count = await opened_count(world, location)

        await world.count_stock_count_line().handle(
            CountStockCountLineCommand(
                counted_quantity=8, stock_count_id=count.id, line_id=count.lines[0].id
            )
        )
        await close_and_confirm(world, count)

        moves = adjustments(world, count)
        assert [m.quantity_delta for m in moves] == [-2]
        # Two of ten from a pool of 300 000 som.
        assert money(world, count)[0].amount == -uzs("60000")

    async def test_an_uncounted_line_adjusts_nothing(self):
        """FR-6.2: a shelf nobody looked at is not a shelf found empty."""
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="50000",
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 10, uzs("300000"))
        count = await opened_count(world, location)

        await close_and_confirm(world, count)

        assert adjustments(world, count) == []

    async def test_counting_zero_books_the_whole_shelf_as_lost(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="50000",
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 10, uzs("300000"))
        count = await opened_count(world, location)

        await world.count_stock_count_line().handle(
            CountStockCountLineCommand(
                counted_quantity=0, stock_count_id=count.id, line_id=count.lines[0].id
            )
        )
        await close_and_confirm(world, count)

        assert money(world, count)[0].amount == -uzs("300000")

    async def test_a_barcode_scan_bumps_the_tally_by_one(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="50000",
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 10, uzs("300000"))
        count = await opened_count(world, location)

        await scan(world, count, CASE_BARCODE)
        result = await scan(world, count, CASE_BARCODE)

        assert result.data is not None
        assert result.data.line is not None
        assert result.data.line.counted_quantity == 2

    async def test_the_adjustment_is_measured_against_the_live_level(self):
        """Cases sold while the count sat open must not be booked a second
        time as a shortage.

        The snapshot said 10, three sold, the shelf holds 7 and the counter
        writes 7. Posting the *report* figure (7 against 10) would take
        another three out and leave the level at 4 under a correct shelf —
        and no verifier would catch it, because the level would be a
        faithful projection of a movement that should never have existed.
        """
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="50000",
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 10, uzs("300000"))
        count = await opened_count(world, location)

        invoice = await world.create_sales_invoice().handle(
            CreateSalesInvoiceCommand(location_id=location.id)
        )
        assert invoice.data is not None
        for _ in range(3):
            await world.scan_invoice_line().handle(
                ScanInvoiceLineCommand(code=CASE_BARCODE, sales_invoice_id=invoice.data.id)
            )
        await world.confirm_sales_invoice().handle(
            ConfirmSalesInvoiceCommand(sales_invoice_id=invoice.data.id)
        )

        await world.count_stock_count_line().handle(
            CountStockCountLineCommand(
                counted_quantity=7, stock_count_id=count.id, line_id=count.lines[0].id
            )
        )
        await close_and_confirm(world, count)

        level = await world.levels.find_one(StockLevelForPair(case.id, location.id))
        assert level is not None
        assert level.quantity == 7
        # The books were already right, so the count adjusts nothing.
        assert adjustments(world, count) == []

    async def test_the_report_still_shows_what_the_counter_saw(self):
        """``delta`` on the line is the report figure and stays measured
        against the snapshot — the poster's arithmetic is its own."""
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="50000",
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 10, uzs("300000"))
        count = await opened_count(world, location)

        result = await world.count_stock_count_line().handle(
            CountStockCountLineCommand(
                counted_quantity=7, stock_count_id=count.id, line_id=count.lines[0].id
            )
        )

        assert result.data is not None
        assert result.data.lines[0].expected_quantity == 10
        assert result.data.lines[0].delta == -3

    async def test_a_surplus_the_pool_cannot_value_is_refused(self):
        """A free accessory would dilute the average for every later sale,
        invisibly and forever."""
        world = make_world()
        location = a_place(world)
        catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="50000",
            barcode=CASE_BARCODE,
        )
        count = await opened_count(world, location)
        await scan(world, count, CASE_BARCODE)
        await world.close_stock_count().handle(
            CloseStockCountCommand(stock_count_id=count.id)
        )

        with pytest.raises(UnpricedUnitError, match="never held any"):
            await world.confirm_stock_count().handle(
                ConfirmStockCountCommand(stock_count_id=count.id)
            )


class TestClosingIsASeparateAct:
    async def test_a_count_cannot_be_confirmed_before_it_is_closed(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        count = await opened_count(world, location)

        with pytest.raises(CountNotClosedError):
            await world.confirm_stock_count().handle(
                ConfirmStockCountCommand(stock_count_id=count.id)
            )

    async def test_a_closed_count_takes_no_more_scans(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        count = await opened_count(world, location)
        await world.close_stock_count().handle(
            CloseStockCountCommand(stock_count_id=count.id)
        )

        with pytest.raises(CountAlreadyClosedError):
            await scan(world, count, PHONE_IMEI)

    async def test_closing_writes_to_neither_ledger(self):
        """Reporting and applying are separate acts by separate people."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        count = await opened_count(world, location)

        await world.close_stock_count().handle(
            CloseStockCountCommand(stock_count_id=count.id)
        )

        assert adjustments(world, count) == []
        assert money(world, count) == []


class TestUndoingAScan:
    async def test_an_expected_handset_goes_back_to_missing(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        count = await opened_count(world, location)
        await scan(world, count, PHONE_IMEI)

        await world.unscan_stock_count_unit().handle(
            UnscanStockCountUnitCommand(stock_count_id=count.id, imei=PHONE_IMEI)
        )

        assert count.units[0].outcome is CountOutcome.MISSING

    async def test_a_surprise_is_removed_outright(self):
        """Its row exists only because somebody scanned it."""
        world = make_world()
        location = a_place(world)
        catalogued(world)
        count = await opened_count(world, location)
        await scan(world, count, UNKNOWN_IMEI)

        await world.unscan_stock_count_unit().handle(
            UnscanStockCountUnitCommand(stock_count_id=count.id, imei=UNKNOWN_IMEI)
        )

        assert count.units == []


class TestCancellingCompensates:
    async def test_a_handset_written_off_by_a_count_comes_back(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        hidden = await in_stock(world, product, location)
        count = await opened_count(world, location)
        await close_and_confirm(world, count)

        await world.cancel_stock_count().handle(
            CancelStockCountCommand(stock_count_id=count.id, reason="miscounted")
        )

        back = await world.units.get(hidden.id)
        assert back is not None
        assert back.status is DeviceStatus.IN_STOCK
        assert back.location_id == location.id

    async def test_the_adjustments_net_to_zero_and_both_sets_stay(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location, cost="380")
        count = await opened_count(world, location)
        await close_and_confirm(world, count)

        await world.cancel_stock_count().handle(
            CancelStockCountCommand(stock_count_id=count.id)
        )

        moves = adjustments(world, count)
        booked = money(world, count)
        assert len(moves) == 2
        assert sum(m.quantity_delta for m in moves) == 0
        assert booked[0].amount + booked[1].amount == usd("0")

    async def test_a_surprise_handsets_row_survives_but_the_store_stops_holding_it(self):
        """Deleting the unit would destroy the record that somebody once
        scanned that IMEI here, which is the evidence §4.3 exists to keep."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        count = await opened_count(world, location)
        await scan(world, count, UNKNOWN_IMEI, product_id=product.id, acquisition_cost="300")
        await close_and_confirm(world, count)

        await world.cancel_stock_count().handle(
            CancelStockCountCommand(stock_count_id=count.id)
        )

        created = await world.units.find_one(DeviceUnitByImei(UNKNOWN_IMEI))
        assert created is not None
        assert created.status is DeviceStatus.WRITTEN_OFF


class TestCostIsShapedByPermission:
    """FR-1.7: a Storekeeper runs counts and does not see costs (§2.1)."""

    async def test_a_storekeeper_reads_the_whole_report_without_the_cost(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        count = await opened_count(world, location)
        await world.scan_stock_count_unit().handle(
            ScanStockCountUnitCommand(
                code=UNKNOWN_IMEI,
                stock_count_id=count.id,
                product_id=product.id,
            )
        )
        count.units[0].acquisition_cost = usd("300")

        result = await world.list_stock_counts().handle(ListStockCountsQuery())

        assert result.data is not None
        unit = result.data[0].units[0]
        assert unit.outcome is CountOutcome.UNEXPECTED
        assert unit.acquisition_cost is None

    async def test_a_manager_sees_it(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        count = await opened_count(world, location)
        await world.scan_stock_count_unit().handle(
            ScanStockCountUnitCommand(
                code=UNKNOWN_IMEI, stock_count_id=count.id, product_id=product.id
            )
        )
        count.units[0].acquisition_cost = usd("300")

        result = await world.list_stock_counts(
            None, Permission.COST_VIEW
        ).handle(ListStockCountsQuery())

        assert result.data is not None
        assert result.data[0].units[0].acquisition_cost.minor == 30_000
