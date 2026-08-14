"""Receiving goods end to end through the handlers — PRD §5.3.

No database: the whole M4 flow runs against the in-memory fakes, which is
the claim §7.3 makes about the application layer. What these cover that
the domain tests cannot is everything needing a lookup — a duplicate IMEI
already in stock, the two ledgers, the unit that comes out the other side,
and what each role is allowed to see.
"""

from uuid import uuid4

import pytest

from application.commands.cancel_goods_receipt import CancelGoodsReceiptCommand
from application.commands.confirm_goods_receipt import ConfirmGoodsReceiptCommand
from application.commands.create_goods_receipt import (
    CreateGoodsReceiptCommand,
    ReceiptLine,
)
from application.commands.price_receipt_unit import PriceReceiptUnitCommand
from application.commands.scan_receipt_unit import ScanReceiptUnitCommand
from application.commands.unscan_receipt_unit import UnscanReceiptUnitCommand
from application.errors import DuplicateImeiError, NotFoundError
from application.queries.get_goods_receipt import GetGoodsReceiptQuery
from domain.entities import Location, Product, Supplier
from domain.enums import (
    AcquisitionSource,
    DeviceCondition,
    DeviceStatus,
    DocumentStatus,
    DocumentType,
    MovementType,
    TrackingType,
    TransactionType,
)
from domain.errors import (
    DocumentNotConfirmedError,
    DocumentNotDraftError,
    InvalidIMEIError,
    ReceiptIncompleteError,
    UnpricedUnitError,
)
from domain.permissions import Permission
from domain.value_objects import SKU, Currency, Money
from tests.application.builders import World, make_world

IMEIS = ["490154203237518", "356938035643809", "352099001761481", "013269009999998"]


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def uzs(major: str) -> Money:
    return Money.from_major(major, Currency.UZS)


def catalogued(
    world: World,
    sku: str = "IP15P-256",
    tracking: TrackingType = TrackingType.SERIAL,
    currency: Currency = Currency.USD,
) -> Product:
    product = Product(
        sku=SKU.parse(sku),
        name="iPhone 15 Pro",
        tracking_type=tracking,
        currency=currency,
        is_active=True,
        created_at=world.clock.now(),
    )
    world.products.by_id[product.id] = product
    return product


def a_place(world: World) -> Location:
    location = Location(name="Shop", is_active=True, created_at=world.clock.now())
    world.locations.by_id[location.id] = location
    return location


def a_supplier(world: World) -> Supplier:
    supplier = Supplier(name="Tashkent Mobile", is_active=True, created_at=world.clock.now())
    world.suppliers.by_id[supplier.id] = supplier
    return supplier


async def opened(
    world: World,
    *,
    source: AcquisitionSource = AcquisitionSource.SUPPLIER,
    lines: list[ReceiptLine] | None = None,
    actor=None,
    **overrides,
):
    """A draft receipt for one serialized product, unless told otherwise."""
    location = overrides.pop("location", None) or a_place(world)
    product = overrides.pop("product", None) or catalogued(world)
    supplier = a_supplier(world) if source is AcquisitionSource.SUPPLIER else None
    result = await world.create_goods_receipt(actor).handle(
        CreateGoodsReceiptCommand(
            location_id=location.id,
            acquisition_source=source,
            supplier_id=supplier.id if supplier else None,
            lines=lines or [ReceiptLine(product_id=product.id, quantity=1)],
            **overrides,
        )
    )
    assert result.data is not None
    return await world.receipts.get(result.data.id), product, location


async def scan(world: World, receipt, imei: str = IMEIS[0], actor=None, **fields):
    return await world.scan_receipt_unit(actor, Permission.PRICING_SET).handle(
        ScanReceiptUnitCommand(imei=imei, goods_receipt_id=receipt.id, **fields)
    )


async def confirm(world: World, receipt, actor=None):
    return await world.confirm_goods_receipt(actor, Permission.COST_VIEW).handle(
        ConfirmGoodsReceiptCommand(goods_receipt_id=receipt.id)
    )


class TestOpeningAReceipt:
    async def test_a_trade_in_saves_with_no_supplier(self):
        world = make_world()
        receipt, _, _ = await opened(world, source=AcquisitionSource.TRADE_IN)

        assert receipt.acquisition_source is AcquisitionSource.TRADE_IN
        assert receipt.supplier_id is None

    async def test_it_is_numbered_when_the_draft_is_opened(self):
        world = make_world()
        first, _, location = await opened(world)
        second, _, _ = await opened(world, location=location)

        assert first.number == "GR-2026-0001"
        assert second.number == "GR-2026-0002"

    async def test_an_unknown_location_is_refused(self):
        world = make_world()
        product = catalogued(world)
        supplier = a_supplier(world)

        with pytest.raises(NotFoundError, match="location"):
            await world.create_goods_receipt().handle(
                CreateGoodsReceiptCommand(
                    location_id=uuid4(),
                    supplier_id=supplier.id,
                    lines=[ReceiptLine(product_id=product.id, quantity=1)],
                )
            )


class TestScanning:
    async def test_a_malformed_imei_never_reaches_the_receipt(self):
        """FR-3.4: the Luhn check digit is not optional."""
        world = make_world()
        receipt, _, _ = await opened(world)

        with pytest.raises(InvalidIMEIError):
            await scan(world, receipt, "490154203237519")

    async def test_scanner_input_is_tolerated(self):
        world = make_world()
        receipt, _, _ = await opened(world)

        result = await scan(world, receipt, "49 015420-323 7518")

        assert result.data is not None
        assert result.data.unit.imei == IMEIS[0]

    async def test_a_double_fire_is_a_no_op_not_an_error(self):
        """§6: scanners double-fire, and punishing that trains the operator
        to ignore the screen."""
        world = make_world()
        receipt, _, _ = await opened(world)

        await scan(world, receipt, IMEIS[0])
        again = await scan(world, receipt, IMEIS[0])

        assert again.data is not None
        assert again.data.scanned_count == 1

    async def test_an_imei_already_in_stock_is_refused_with_where_it_is(self):
        """FR-3.5: a duplicate is a mis-scan or a stolen-goods red flag."""
        world = make_world()
        first, product, location = await opened(world)
        await scan(world, first, IMEIS[0], acquisition_cost="700")
        await confirm(world, first)

        second, _, _ = await opened(world, product=product, location=location)
        with pytest.raises(DuplicateImeiError, match="in_stock"):
            await scan(world, second, IMEIS[0])

    async def test_scanning_past_the_declared_quantity_is_refused(self):
        world = make_world()
        receipt, _, _ = await opened(world)

        await scan(world, receipt, IMEIS[0])
        with pytest.raises(ReceiptIncompleteError, match="1 of 1"):
            await scan(world, receipt, IMEIS[1])

    async def test_a_scan_can_be_undone_while_the_receipt_is_a_draft(self):
        world = make_world()
        receipt, _, _ = await opened(world)
        await scan(world, receipt, IMEIS[0])

        await world.unscan_receipt_unit().handle(
            UnscanReceiptUnitCommand(goods_receipt_id=receipt.id, imei=IMEIS[0])
        )

        reloaded = await world.receipts.get(receipt.id)
        assert reloaded is not None and reloaded.units() == []


class TestPricingAtIntake:
    async def test_a_storekeeper_scans_and_a_manager_prices(self):
        """FR-3.4b: the two acts genuinely belong to two people."""
        world = make_world()
        receipt, _, _ = await opened(world)
        await world.scan_receipt_unit().handle(
            ScanReceiptUnitCommand(
                imei=IMEIS[0],
                condition=DeviceCondition.USED,
                goods_receipt_id=receipt.id,
            )
        )

        with pytest.raises(UnpricedUnitError):
            await confirm(world, receipt)

        await world.price_receipt_unit(None, Permission.PRICING_SET).handle(
            PriceReceiptUnitCommand(
                acquisition_cost="410",
                asking_price="520",
                goods_receipt_id=receipt.id,
                imei=IMEIS[0],
            )
        )
        await confirm(world, receipt)

        unit = await world.units.get_by_imei(IMEIS[0])
        assert unit is not None
        assert unit.acquisition_cost == usd("410")
        assert unit.asking_price == usd("520")

    async def test_the_price_is_denominated_by_the_product_not_the_caller(self):
        world = make_world()
        product = catalogued(world, "CASE-1", TrackingType.QUANTITY, Currency.UZS)
        receipt, _, _ = await opened(
            world,
            product=product,
            lines=[ReceiptLine(product_id=product.id, quantity=5, unit_cost="10000")],
        )

        assert receipt is not None
        assert receipt.lines[0].unit_cost == uzs("10000")


class TestConfirming:
    async def test_it_creates_the_handset_and_writes_both_ledgers(self):
        """FR-3.7 and FR-10.1: goods and money in one act."""
        world = make_world()
        receipt, product, location = await opened(world)
        await scan(world, receipt, IMEIS[0], acquisition_cost="700")

        await confirm(world, receipt)

        unit = await world.units.get_by_imei(IMEIS[0])
        assert unit is not None
        assert unit.status is DeviceStatus.IN_STOCK
        assert unit.location_id == location.id
        assert unit.source_document_type is DocumentType.GOODS_RECEIPT
        assert unit.source_document_id == receipt.id

        movement = world.movements.rows[0]
        assert movement.movement_type is MovementType.RECEIPT
        assert movement.quantity_delta == 1
        assert movement.product_id == product.id

        entry = world.transactions.rows[0]
        assert entry.txn_type is TransactionType.PURCHASE
        assert entry.amount == -usd("700")

    async def test_a_quantity_line_moves_the_level_by_the_whole_line(self):
        world = make_world()
        product = catalogued(world, "CASE-1", TrackingType.QUANTITY, Currency.UZS)
        receipt, _, location = await opened(
            world,
            product=product,
            lines=[ReceiptLine(product_id=product.id, quantity=5, unit_cost="10000")],
        )

        await confirm(world, receipt)

        level = await world.levels.get_for(product.id, location.id)
        assert level is not None and level.quantity == 5
        assert world.transactions.rows[0].amount == -uzs("50000")

    async def test_an_intake_price_starts_the_handsets_price_log(self):
        """FR-3.11: the log is complete from the unit's first moment."""
        world = make_world()
        receipt, _, _ = await opened(world)
        await scan(
            world,
            receipt,
            IMEIS[0],
            condition=DeviceCondition.USED,
            acquisition_cost="410",
            asking_price="520",
        )

        await confirm(world, receipt)

        unit = await world.units.get_by_imei(IMEIS[0])
        assert unit is not None
        changes = await world.unit_price_changes.list_for_unit(unit.id)
        assert len(changes) == 1
        assert changes[0].old_price is None
        assert changes[0].new_price == usd("520")

    async def test_a_confirmed_receipt_cannot_be_scanned_onto(self):
        world = make_world()
        receipt, _, _ = await opened(world)
        await scan(world, receipt, IMEIS[0], acquisition_cost="700")
        await confirm(world, receipt)

        with pytest.raises(DocumentNotDraftError):
            await scan(world, receipt, IMEIS[1])


class TestTheSomPaidTradeIn:
    async def test_the_ledger_books_the_dollars_and_never_the_som(self):
        """FR-3.4c's stated test: received at $330 with 4 200 000 so'm
        handed over. No figure anywhere equals or contains 4 200 000."""
        world = make_world()
        receipt, _, _ = await opened(world, source=AcquisitionSource.TRADE_IN)
        await scan(
            world,
            receipt,
            IMEIS[0],
            condition=DeviceCondition.USED,
            acquisition_cost="330",
            asking_price="420",
            cash_paid="4200000",
            cash_paid_currency=Currency.UZS,
        )

        await confirm(world, receipt)

        assert [t.amount for t in world.transactions.rows] == [-usd("330")]
        unit = await world.units.get_by_imei(IMEIS[0])
        assert unit is not None
        assert unit.acquisition_cost == usd("330")
        assert unit.cash_paid_minor == 4_200_000
        assert unit.cash_paid_currency is Currency.UZS
        assert all(
            t.amount.amount_minor != 4_200_000 for t in world.transactions.rows
        )


class TestCancelling:
    async def test_it_compensates_both_ledgers_and_keeps_the_originals(self):
        world = make_world()
        receipt, _, _ = await opened(world)
        await scan(world, receipt, IMEIS[0], acquisition_cost="700")
        await confirm(world, receipt)

        await world.cancel_goods_receipt(None, Permission.COST_VIEW).handle(
            CancelGoodsReceiptCommand(goods_receipt_id=receipt.id, reason="wrong van")
        )

        assert len(world.movements.rows) == 2
        assert sum(m.quantity_delta for m in world.movements.rows) == 0
        assert len(world.transactions.rows) == 2
        assert sum(t.amount.amount_minor for t in world.transactions.rows) == 0

    async def test_the_handset_lands_in_receipt_cancelled_not_written_off(self):
        """The store lost nothing, so a write-off report must not count it."""
        world = make_world()
        receipt, _, _ = await opened(world)
        await scan(world, receipt, IMEIS[0], acquisition_cost="700")
        await confirm(world, receipt)

        await world.cancel_goods_receipt(None, Permission.COST_VIEW).handle(
            CancelGoodsReceiptCommand(goods_receipt_id=receipt.id)
        )

        unit = await world.units.get_by_imei(IMEIS[0])
        assert unit is not None
        assert unit.status is DeviceStatus.RECEIPT_CANCELLED
        assert unit.location_id is None
        assert not unit.status.is_on_hand

    async def test_a_receipt_cannot_be_cancelled_twice(self):
        world = make_world()
        receipt, _, _ = await opened(world)
        await scan(world, receipt, IMEIS[0], acquisition_cost="700")
        await confirm(world, receipt)
        canceller = world.cancel_goods_receipt(None, Permission.COST_VIEW)
        await canceller.handle(CancelGoodsReceiptCommand(goods_receipt_id=receipt.id))

        with pytest.raises(DocumentNotConfirmedError):
            await canceller.handle(
                CancelGoodsReceiptCommand(goods_receipt_id=receipt.id)
            )

        # The reversal ran once, not twice: two movements, not four.
        assert len(world.movements.rows) == 2


class TestWhatEachRoleSees:
    """FR-1.7: response shaping, not UI hiding."""

    async def test_a_storekeeper_sees_the_asking_price_and_no_cost(self):
        world = make_world()
        receipt, _, _ = await opened(world)
        await scan(
            world,
            receipt,
            IMEIS[0],
            condition=DeviceCondition.USED,
            acquisition_cost="410",
            asking_price="520",
            cash_paid="5000000",
            cash_paid_currency=Currency.UZS,
        )

        seen = await world.get_goods_receipt().handle(
            GetGoodsReceiptQuery(goods_receipt_id=receipt.id)
        )

        assert seen.data is not None
        unit = seen.data.lines[0].units[0]
        assert unit.asking_price is not None
        assert unit.acquisition_cost is None
        assert unit.acquisition_cost_minor is None
        assert unit.cash_paid is None
        assert seen.data.subtotals == []

    async def test_a_manager_sees_the_cost_and_the_som_handed_over(self):
        world = make_world()
        receipt, _, _ = await opened(world)
        await scan(
            world,
            receipt,
            IMEIS[0],
            condition=DeviceCondition.USED,
            acquisition_cost="410",
            asking_price="520",
            cash_paid="5000000",
            cash_paid_currency=Currency.UZS,
        )

        seen = await world.get_goods_receipt(None, Permission.COST_VIEW).handle(
            GetGoodsReceiptQuery(goods_receipt_id=receipt.id)
        )

        assert seen.data is not None
        unit = seen.data.lines[0].units[0]
        assert unit.acquisition_cost_minor == 41_000
        assert unit.cash_paid == uzs("5000000").format()
        assert [s.amount_minor for s in seen.data.subtotals] == [41_000]

    async def test_an_unpriced_used_handset_is_flagged_to_whoever_scanned_it(self):
        """The Storekeeper cannot price it, but can see what is blocking
        the confirm and go and find someone who can."""
        world = make_world()
        receipt, _, _ = await opened(world, lines=None)
        await world.scan_receipt_unit().handle(
            ScanReceiptUnitCommand(
                imei=IMEIS[0],
                condition=DeviceCondition.USED,
                goods_receipt_id=receipt.id,
            )
        )

        seen = await world.get_goods_receipt().handle(
            GetGoodsReceiptQuery(goods_receipt_id=receipt.id)
        )

        assert seen.data is not None
        assert seen.data.lines[0].units[0].needs_asking_price is True
        assert seen.data.status is DocumentStatus.DRAFT
