"""Selling end to end through the handlers — PRD §5.4.

No database: the whole M5 flow runs against the in-memory fakes. What
these cover that the domain tests cannot is everything needing a lookup —
resolving a price against the live unit and the live catalog row, the two
ledgers, what happens to the handset, and the refusals that only a query
can reach.

The first class is the one that matters most. §11 names *"a used unit
silently inheriting the new-goods catalog price"* the signature bug of
bolting used stock onto a new-goods catalog, and it is invisible when it
happens: a plausible number lands on the invoice and the margin report
shows profit that never existed.
"""

from uuid import uuid4

import pytest

from application.commands.add_invoice_accessory_line import (
    AddInvoiceAccessoryLineCommand,
)
from application.commands.cancel_sales_invoice import CancelSalesInvoiceCommand
from application.commands.confirm_sales_invoice import ConfirmSalesInvoiceCommand
from application.commands.create_sales_invoice import CreateSalesInvoiceCommand
from application.commands.override_invoice_line_price import (
    OverrideInvoiceLinePriceCommand,
)
from application.commands.scan_invoice_line import ScanInvoiceLineCommand
from application.commands.unscan_invoice_line import UnscanInvoiceLineCommand
from application.dtos import MoneyEffect, Posting, PostingEntry
from application.errors import NotFoundError
from domain.entities import DeviceUnit, Location, Product
from domain.enums import (
    DeviceCondition,
    DeviceStatus,
    DocumentStatus,
    DocumentType,
    MovementType,
    TrackingType,
    TransactionType,
)
from domain.errors import (
    DocumentNotDraftError,
    InsufficientStockError,
    PriceNotSetError,
    UnitNotSellableError,
    WrongLocationError,
)
from domain.value_objects import IMEI, SKU, Barcode, Currency, Money
from tests.application.builders import World, make_world

PHONE_IMEI = "490154203237518"
OTHER_IMEI = "356938035643809"
CASE_BARCODE = "4006381333931"


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def uzs(major: str) -> Money:
    return Money.from_major(major, Currency.UZS)


def a_place(world: World, name: str = "Shop") -> Location:
    location = Location(name=name, is_active=True, created_at=world.clock.now())
    world.locations.by_id[location.id] = location
    return location


def catalogued(
    world: World,
    *,
    sku: str = "IP15P-256",
    price: str | None = "900",
    tracking: TrackingType = TrackingType.SERIAL,
    currency: Currency = Currency.USD,
    barcode: str | None = None,
) -> Product:
    product = Product(
        sku=SKU.parse(sku),
        name="iPhone 15 Pro",
        tracking_type=tracking,
        currency=currency,
        barcode=Barcode.parse(barcode) if barcode else None,
        default_sale_price=None if price is None else Money.from_major(price, currency),
        is_active=True,
        created_at=world.clock.now(),
    )
    world.products.by_id[product.id] = product
    return product


async def in_stock(
    world: World,
    product: Product,
    location: Location,
    *,
    imei: str = PHONE_IMEI,
    cost: str = "380",
    condition: DeviceCondition = DeviceCondition.NEW,
    asking: str | None = None,
) -> DeviceUnit:
    """A handset on the shelf, with the movement that put it there.

    Posted through ``LedgerPoster`` rather than the M4 receipt flow, the
    same way ``tests/api/ledger_helpers.py`` does: FR-3.10 refuses to
    confirm a receipt holding an unpriced used handset, and that handset
    is exactly the state FR-4.2b exists to refuse at the counter (a stock
    count creates one, FR-6.4b). It still writes the ``+1`` movement,
    because a unit in stock with no movement behind it breaks §4.3 rule 1
    and would make the cancel reprojection read a truncated history.
    """
    unit = DeviceUnit(
        imei=IMEI.parse(imei),
        product_id=product.id,
        status=DeviceStatus.IN_STOCK,
        location_id=location.id,
        acquisition_cost=Money.from_major(cost, product.currency),
        asking_price=None if asking is None else Money.from_major(asking, product.currency),
        condition=condition,
        created_at=world.clock.now(),
    )
    world.units.by_id[unit.id] = unit
    await world.poster().post(
        Posting(
            document_type=DocumentType.GOODS_RECEIPT,
            document_id=uuid4(),
            entries=[
                PostingEntry(
                    movement_type=MovementType.RECEIPT,
                    product_id=product.id,
                    location_id=location.id,
                    quantity_delta=1,
                    device_unit_id=unit.id,
                    new_status=DeviceStatus.IN_STOCK,
                    new_location_id=location.id,
                    money=[MoneyEffect(TransactionType.PURCHASE, -unit.acquisition_cost)],
                )
            ],
        )
    )
    return unit


async def stocked_accessory(
    world: World, product: Product, location: Location, quantity: int, total_cost: Money
) -> None:
    """Accessories arrive through the ledger, because their cost pool is
    replayed from it rather than stored (§4.6)."""
    await world.poster().post(
        Posting(
            document_type=DocumentType.GOODS_RECEIPT,
            document_id=uuid4(),
            entries=[
                PostingEntry(
                    movement_type=MovementType.RECEIPT,
                    product_id=product.id,
                    location_id=location.id,
                    quantity_delta=quantity,
                    money=[MoneyEffect(TransactionType.PURCHASE, -total_cost)],
                )
            ],
        )
    )


async def opened(world: World, location: Location, actor=None, **overrides):
    result = await world.create_sales_invoice(actor).handle(
        CreateSalesInvoiceCommand(location_id=location.id, **overrides)
    )
    assert result.data is not None
    invoice = await world.invoices.get(result.data.id)
    assert invoice is not None
    return invoice


async def scan(world: World, invoice, code: str):
    return await world.scan_invoice_line().handle(
        ScanInvoiceLineCommand(code=code, sales_invoice_id=invoice.id)
    )


async def confirm(world: World, invoice, actor=None):
    return await world.confirm_sales_invoice(actor).handle(
        ConfirmSalesInvoiceCommand(sales_invoice_id=invoice.id)
    )


class TestAUsedHandsetNeverInheritsTheCatalogPrice:
    """FR-2.14, FR-4.2b, and §11's high-severity risk row."""

    async def test_an_unpriced_used_unit_is_refused_at_the_counter(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        await in_stock(world, product, location, condition=DeviceCondition.USED)
        invoice = await opened(world, location)

        with pytest.raises(PriceNotSetError):
            await scan(world, invoice, PHONE_IMEI)

    async def test_the_refusal_creates_no_line(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        await in_stock(world, product, location, condition=DeviceCondition.USED)
        invoice = await opened(world, location)

        with pytest.raises(PriceNotSetError):
            await scan(world, invoice, PHONE_IMEI)

        assert invoice.lines == []

    async def test_the_message_names_who_can_fix_it(self):
        """The Seller who hits this cannot price the handset themselves —
        pricing is Owner/Manager (§2.1), so the error has to say so."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        await in_stock(world, product, location, condition=DeviceCondition.USED)
        invoice = await opened(world, location)

        with pytest.raises(PriceNotSetError, match="Owner or Manager"):
            await scan(world, invoice, PHONE_IMEI)

    async def test_pricing_the_unit_then_makes_it_sellable_at_its_own_price(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        await in_stock(world, product, location, condition=DeviceCondition.USED, asking="500")
        invoice = await opened(world, location)

        result = await scan(world, invoice, PHONE_IMEI)

        assert result.data is not None
        assert result.data.resolved_price.minor == usd("500").amount_minor

    async def test_a_new_unit_with_no_price_of_its_own_takes_the_catalog_price(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        await in_stock(world, product, location, condition=DeviceCondition.NEW)
        invoice = await opened(world, location)

        result = await scan(world, invoice, PHONE_IMEI)

        assert result.data is not None
        assert result.data.resolved_price.minor == usd("900").amount_minor


class TestScanningChecksTheGoodsAreHere:
    async def test_a_sold_handset_is_refused_naming_its_status(self):
        """FR-4.3: you cannot sell a phone that is already sold."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        unit = await in_stock(world, product, location)
        unit.status = DeviceStatus.SOLD
        unit.location_id = None
        invoice = await opened(world, location)

        with pytest.raises(UnitNotSellableError, match="sold"):
            await scan(world, invoice, PHONE_IMEI)

    async def test_a_handset_at_another_location_is_refused(self):
        """FR-4.4: a sale takes stock from the place the invoice names."""
        world = make_world()
        warehouse, shop = a_place(world, "Warehouse"), a_place(world, "Shop")
        product = catalogued(world)
        await in_stock(world, product, warehouse)
        invoice = await opened(world, shop)

        with pytest.raises(WrongLocationError):
            await scan(world, invoice, PHONE_IMEI)

    async def test_an_unknown_code_is_a_not_found_rather_than_an_empty_answer(self):
        """FR-7.4, applied at the till."""
        world = make_world()
        invoice = await opened(world, a_place(world))

        with pytest.raises(NotFoundError):
            await scan(world, invoice, "9999999999999")

    async def test_a_confirmed_invoice_takes_no_more_scans(self):
        """FR-4.5d: a wrong confirmed invoice is cancelled and re-entered."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        await in_stock(world, product, location, imei=OTHER_IMEI)
        invoice = await opened(world, location)
        await scan(world, invoice, PHONE_IMEI)
        await confirm(world, invoice)

        with pytest.raises(DocumentNotDraftError):
            await scan(world, invoice, OTHER_IMEI)


class TestOneBeepIsOneLine:
    async def test_scanning_the_same_imei_twice_changes_nothing(self):
        """§6: scanners double-fire, and punishing that would train the
        operator to ignore the screen."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        invoice = await opened(world, location)

        first = await scan(world, invoice, PHONE_IMEI)
        second = await scan(world, invoice, PHONE_IMEI)

        assert len(invoice.lines) == 1
        assert first.data is not None and second.data is not None
        assert first.data.line.id == second.data.line.id

    async def test_scanning_a_barcode_twice_sells_two(self):
        """A deliberate exception to §6's no-op rule: three identical cases
        across the counter are three sales."""
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="25000",
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 5, uzs("100000"))
        invoice = await opened(world, location)

        await scan(world, invoice, CASE_BARCODE)
        await scan(world, invoice, CASE_BARCODE)

        assert len(invoice.lines) == 1
        assert invoice.lines[0].quantity == 2
        assert invoice.lines[0].product_id == case.id

    async def test_a_serialized_model_scanned_by_sku_is_refused(self):
        """A catalog row names a model, and a sale is of one named handset.

        Reached by SKU rather than barcode because FR-2.3 already forbids a
        barcode on a SERIAL product — the catalog cannot even hold one.
        """
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        invoice = await opened(world, location)

        with pytest.raises(UnitNotSellableError, match="IMEI"):
            await scan(world, invoice, str(product.sku))

    async def test_an_accessory_with_no_catalog_price_is_refused(self):
        """FR-2.12: there is nowhere else a price could come from."""
        world = make_world()
        location = a_place(world)
        catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price=None,
            barcode=CASE_BARCODE,
        )
        invoice = await opened(world, location)

        with pytest.raises(PriceNotSetError):
            await scan(world, invoice, CASE_BARCODE)

    async def test_a_line_comes_off_a_draft_with_no_trace(self):
        """FR-4.5c."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world)
        await in_stock(world, product, location)
        invoice = await opened(world, location)
        scanned = await scan(world, invoice, PHONE_IMEI)
        assert scanned.data is not None

        await world.unscan_invoice_line().handle(
            UnscanInvoiceLineCommand(
                sales_invoice_id=invoice.id, line_id=scanned.data.line.id
            )
        )

        assert invoice.lines == []


class TestAddingAnAccessoryFromTheCatalog:
    """FR-4.2c: the same line a barcode scan makes, added by product id."""

    @staticmethod
    async def add(world: World, invoice, product: Product, quantity: int = 1):
        return await world.add_invoice_accessory_line().handle(
            AddInvoiceAccessoryLineCommand(
                product_id=product.id,
                quantity=quantity,
                sales_invoice_id=invoice.id,
            )
        )

    async def test_a_quantity_lands_as_one_line_at_the_catalog_price(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="25000",
        )
        await stocked_accessory(world, case, location, 10, uzs("200000"))
        invoice = await opened(world, location)

        result = await self.add(world, invoice, case, 3)

        assert result.data is not None
        assert result.data.resolved_price.minor == uzs("25000").amount_minor
        assert len(invoice.lines) == 1
        assert invoice.lines[0].quantity == 3
        assert invoice.lines[0].product_id == case.id

    async def test_the_same_product_again_merges_with_the_scanned_line(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="25000",
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 10, uzs("200000"))
        invoice = await opened(world, location)

        await scan(world, invoice, CASE_BARCODE)
        await self.add(world, invoice, case, 2)

        assert len(invoice.lines) == 1
        assert invoice.lines[0].quantity == 3

    async def test_selling_more_than_is_in_stock_is_refused(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="25000",
        )
        await stocked_accessory(world, case, location, 2, uzs("40000"))
        invoice = await opened(world, location)

        with pytest.raises(InsufficientStockError):
            await self.add(world, invoice, case, 3)
        assert invoice.lines == []

    async def test_a_phone_product_is_refused(self):
        world = make_world()
        location = a_place(world)
        phone = catalogued(world)
        invoice = await opened(world, location)

        with pytest.raises(UnitNotSellableError, match="IMEI"):
            await self.add(world, invoice, phone)

    async def test_an_accessory_with_no_catalog_price_is_refused(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price=None,
        )
        invoice = await opened(world, location)

        with pytest.raises(PriceNotSetError):
            await self.add(world, invoice, case)

    async def test_an_unknown_product_is_a_404(self):
        world = make_world()
        location = a_place(world)
        invoice = await opened(world, location)

        with pytest.raises(NotFoundError):
            await world.add_invoice_accessory_line().handle(
                AddInvoiceAccessoryLineCommand(
                    product_id=uuid4(), sales_invoice_id=invoice.id
                )
            )

    async def test_a_confirmed_invoice_takes_no_new_line(self):
        world = make_world()
        location = a_place(world)
        phone = catalogued(world)
        await in_stock(world, phone, location)
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="25000",
        )
        invoice = await opened(world, location)
        await scan(world, invoice, PHONE_IMEI)
        await confirm(world, invoice)

        with pytest.raises(DocumentNotDraftError):
            await self.add(world, invoice, case)


class TestTheDraftDoesNotReserveAPrice:
    """FR-4.5b1, both halves of its stated test."""

    async def test_a_markdown_while_the_draft_sat_open_reaches_the_customer(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price=None)
        unit = await in_stock(
            world, product, location, condition=DeviceCondition.USED, asking="520"
        )
        invoice = await opened(world, location)
        await scan(world, invoice, PHONE_IMEI)

        unit.asking_price = usd("480")
        await confirm(world, invoice)

        assert invoice.lines[0].charged_price == usd("480")
        assert invoice.deviations() == []

    async def test_an_override_survives_the_markdown_and_reports_the_deviation(self):
        world = make_world()
        location = a_place(world)
        manager = uuid4()
        product = catalogued(world, price=None)
        unit = await in_stock(
            world, product, location, condition=DeviceCondition.USED, asking="520"
        )
        invoice = await opened(world, location)
        scanned = await scan(world, invoice, PHONE_IMEI)
        assert scanned.data is not None

        await world.override_invoice_line_price(manager).handle(
            OverrideInvoiceLinePriceCommand(
                price="300",
                sales_invoice_id=invoice.id,
                line_id=scanned.data.line.id,
            )
        )
        unit.asking_price = usd("480")
        await confirm(world, invoice)

        line = invoice.lines[0]
        assert line.charged_price == usd("300")
        assert line.resolved_price == usd("480")
        assert invoice.deviations() == [line]

    async def test_a_line_that_stops_resolving_fails_the_confirm(self):
        """FR-4.5b2: the unit was flipped to USED while the draft sat open."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        unit = await in_stock(world, product, location, condition=DeviceCondition.NEW)
        invoice = await opened(world, location)
        await scan(world, invoice, PHONE_IMEI)

        unit.condition = DeviceCondition.USED

        with pytest.raises(PriceNotSetError):
            await confirm(world, invoice)

    async def test_that_failure_writes_nothing_to_either_ledger(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        unit = await in_stock(world, product, location, condition=DeviceCondition.NEW)
        invoice = await opened(world, location)
        await scan(world, invoice, PHONE_IMEI)
        unit.condition = DeviceCondition.USED

        with pytest.raises(PriceNotSetError):
            await confirm(world, invoice)

        assert [m for m in world.movements.rows if m.document_id == invoice.id] == []
        assert [t for t in world.transactions.rows if t.document_id == invoice.id] == []


class TestConfirmingMovesGoodsAndMoneyTogether:
    async def test_the_handset_is_sold_and_holds_no_location(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        unit = await in_stock(world, product, location)
        invoice = await opened(world, location)
        await scan(world, invoice, PHONE_IMEI)

        await confirm(world, invoice)

        assert unit.status is DeviceStatus.SOLD
        assert unit.location_id is None

    async def test_one_movement_out_per_line(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        await in_stock(world, product, location)
        invoice = await opened(world, location)
        await scan(world, invoice, PHONE_IMEI)
        await confirm(world, invoice)

        movements = [m for m in world.movements.rows if m.document_id == invoice.id]
        assert [m.quantity_delta for m in movements] == [-1]
        assert movements[0].movement_type is MovementType.SALE
        assert movements[0].document_type is DocumentType.SALES_INVOICE

    async def test_revenue_and_cogs_are_booked_against_the_same_sale(self):
        """§4.6: COGS for a phone is specific identification — this
        phone's own cost, not a model of what phones like it cost."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        await in_stock(world, product, location, cost="380")
        invoice = await opened(world, location)
        await scan(world, invoice, PHONE_IMEI)
        await confirm(world, invoice)

        booked = {
            txn.txn_type: txn.amount
            for txn in world.transactions.rows
            if txn.document_id == invoice.id
        }
        assert booked[TransactionType.SALE_REVENUE] == usd("900")
        assert booked[TransactionType.COGS] == usd("-380")

    async def test_the_ledger_names_the_seller_who_confirmed(self):
        world = make_world()
        location = a_place(world)
        seller = uuid4()
        product = catalogued(world, price="900")
        await in_stock(world, product, location)
        invoice = await opened(world, location)
        await scan(world, invoice, PHONE_IMEI)
        await confirm(world, invoice, actor=seller)

        sale_money = [t for t in world.transactions.rows if t.document_id == invoice.id]
        assert sale_money and all(txn.user_id == seller for txn in sale_money)

    async def test_a_phone_and_an_accessory_report_two_subtotals(self):
        """FR-2.7's stated test: exactly two totals and no field for
        their sum."""
        world = make_world()
        location = a_place(world)
        phone = catalogued(world, price="600")
        case = catalogued(
            world,
            sku="CASE-CLR",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            price="50000",
            barcode=CASE_BARCODE,
        )
        await in_stock(world, phone, location)
        await stocked_accessory(world, case, location, 10, uzs("300000"))
        invoice = await opened(world, location)
        await scan(world, invoice, PHONE_IMEI)
        await scan(world, invoice, CASE_BARCODE)

        await confirm(world, invoice)

        assert invoice.subtotals() == {Currency.USD: usd("600"), Currency.UZS: uzs("50000")}


class TestAccessoriesCostTheirWeightedAverage:
    async def test_cogs_is_the_average_at_the_time_of_sale(self):
        """§4.6: two receipts at different costs, one pool."""
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
        # 10 at 30 000 each, then 10 at 50 000 each: the pool averages 40 000.
        await stocked_accessory(world, case, location, 10, uzs("300000"))
        await stocked_accessory(world, case, location, 10, uzs("500000"))
        invoice = await opened(world, location)
        await scan(world, invoice, CASE_BARCODE)
        await scan(world, invoice, CASE_BARCODE)
        await confirm(world, invoice)

        cogs = next(
            txn.amount
            for txn in world.transactions.rows
            if txn.txn_type is TransactionType.COGS and txn.document_id == invoice.id
        )
        assert cogs == uzs("-80000")

    async def test_selling_more_than_is_here_is_refused_whole(self):
        """FR-4.7: no partial fulfilment."""
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
        await stocked_accessory(world, case, location, 1, uzs("30000"))
        invoice = await opened(world, location)
        scanned = await scan(world, invoice, CASE_BARCODE)
        assert scanned.data is not None
        await world.override_invoice_line_price().handle(
            OverrideInvoiceLinePriceCommand(
                quantity=5, sales_invoice_id=invoice.id, line_id=scanned.data.line.id
            )
        )

        with pytest.raises(InsufficientStockError):
            await confirm(world, invoice)


class TestOverridingOneLine:
    async def test_the_approver_is_the_manager_not_the_confirming_seller(self):
        """FR-4.5f's stated test."""
        world = make_world()
        location = a_place(world)
        manager, seller = uuid4(), uuid4()
        product = catalogued(world, price=None)
        await in_stock(world, product, location, asking="520")
        invoice = await opened(world, location)
        scanned = await scan(world, invoice, PHONE_IMEI)
        assert scanned.data is not None

        await world.override_invoice_line_price(manager).handle(
            OverrideInvoiceLinePriceCommand(
                price="300", sales_invoice_id=invoice.id, line_id=scanned.data.line.id
            )
        )
        await confirm(world, invoice, actor=seller)

        line = invoice.lines[0]
        assert line.resolved_price == usd("520")
        assert line.charged_price == usd("300")
        assert line.price_approved_by == manager
        revenue = next(
            txn
            for txn in world.transactions.rows
            if txn.txn_type is TransactionType.SALE_REVENUE and txn.document_id == invoice.id
        )
        assert revenue.user_id == seller
        assert revenue.amount == usd("300")

    async def test_no_note_is_required(self):
        """FR-4.5g: a field demanded on every small haggle becomes a dash
        within a week and then means nothing."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price=None)
        await in_stock(world, product, location, asking="520")
        invoice = await opened(world, location)
        scanned = await scan(world, invoice, PHONE_IMEI)
        assert scanned.data is not None

        await world.override_invoice_line_price(uuid4()).handle(
            OverrideInvoiceLinePriceCommand(
                price="480", sales_invoice_id=invoice.id, line_id=scanned.data.line.id
            )
        )
        await confirm(world, invoice)

        assert invoice.lines[0].price_note is None
        assert invoice.lines[0].is_deviation is True

    async def test_an_override_never_reprices_the_unit_in_stock(self):
        """FR-4.5's stated test, checked before the cancel even runs."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price=None)
        unit = await in_stock(world, product, location, asking="520")
        invoice = await opened(world, location)
        scanned = await scan(world, invoice, PHONE_IMEI)
        assert scanned.data is not None

        await world.override_invoice_line_price(uuid4()).handle(
            OverrideInvoiceLinePriceCommand(
                price="480", sales_invoice_id=invoice.id, line_id=scanned.data.line.id
            )
        )

        assert unit.asking_price == usd("520")
        assert world.unit_price_changes.rows == []


class TestCancellingCompensates:
    async def test_the_original_rows_stay_and_their_negation_is_appended(self):
        """FR-4.8, §4.3 rule 2: a cancelled sale is two sets of rows,
        not zero."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        await in_stock(world, product, location, cost="380")
        invoice = await opened(world, location)
        await scan(world, invoice, PHONE_IMEI)
        await confirm(world, invoice)

        await world.cancel_sales_invoice().handle(
            CancelSalesInvoiceCommand(sales_invoice_id=invoice.id, reason="changed mind")
        )

        sale_movements = [m for m in world.movements.rows if m.document_id == invoice.id]
        sale_money = [t for t in world.transactions.rows if t.document_id == invoice.id]

        assert [m.quantity_delta for m in sale_movements] == [-1, 1]
        assert len(sale_money) == 4
        assert sum((txn.amount for txn in sale_money), usd("0")) == usd("0")

    async def test_the_handset_comes_back_to_the_shelf_where_it_was(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        unit = await in_stock(world, product, location)
        invoice = await opened(world, location)
        await scan(world, invoice, PHONE_IMEI)
        await confirm(world, invoice)

        await world.cancel_sales_invoice().handle(
            CancelSalesInvoiceCommand(sales_invoice_id=invoice.id)
        )

        assert unit.status is DeviceStatus.IN_STOCK
        assert unit.location_id == location.id

    async def test_it_comes_back_asking_what_it_always_asked(self):
        """FR-4.5's stated test: override a line, cancel the invoice, and
        the unit is untouched."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price=None)
        unit = await in_stock(world, product, location, asking="520")
        invoice = await opened(world, location)
        scanned = await scan(world, invoice, PHONE_IMEI)
        assert scanned.data is not None
        await world.override_invoice_line_price(uuid4()).handle(
            OverrideInvoiceLinePriceCommand(
                price="480", sales_invoice_id=invoice.id, line_id=scanned.data.line.id
            )
        )
        await confirm(world, invoice)

        await world.cancel_sales_invoice().handle(
            CancelSalesInvoiceCommand(sales_invoice_id=invoice.id)
        )

        assert unit.status is DeviceStatus.IN_STOCK
        assert unit.asking_price == usd("520")

    async def test_a_cancelled_sale_frees_the_handset_for_another_invoice(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        await in_stock(world, product, location)
        first = await opened(world, location)
        await scan(world, first, PHONE_IMEI)
        await confirm(world, first)
        await world.cancel_sales_invoice().handle(
            CancelSalesInvoiceCommand(sales_invoice_id=first.id)
        )

        second = await opened(world, location)
        await scan(world, second, PHONE_IMEI)
        await confirm(world, second)

        assert second.status is DocumentStatus.CONFIRMED


class TestADraftReservesNothingAcrossInvoices:
    async def test_two_drafts_may_hold_the_same_handset(self):
        """§4.4: a draft is a shopping list and touches nothing."""
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        await in_stock(world, product, location)
        first, second = await opened(world, location), await opened(world, location)

        await scan(world, first, PHONE_IMEI)
        await scan(world, second, PHONE_IMEI)

        assert len(first.lines) == 1
        assert len(second.lines) == 1

    async def test_only_the_first_confirm_wins(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="900")
        await in_stock(world, product, location)
        first, second = await opened(world, location), await opened(world, location)
        await scan(world, first, PHONE_IMEI)
        await scan(world, second, PHONE_IMEI)

        await confirm(world, first)

        with pytest.raises(UnitNotSellableError):
            await confirm(world, second)
