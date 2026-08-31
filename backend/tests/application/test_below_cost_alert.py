"""BelowCostChecker — accessories whose weighted-average cost has caught up
to their catalog price (FR-2.15)."""

from uuid import uuid4

import pytest

from application.commands.confirm_goods_receipt import ConfirmGoodsReceiptCommand
from application.commands.create_goods_receipt import (
    CreateGoodsReceiptCommand,
    ReceiptLine,
)
from application.commands.scan_receipt_unit import ScanReceiptUnitCommand
from application.dtos import BelowCostRow
from application.queries.list_below_cost import (
    ListBelowCostHandler,
    ListBelowCostQuery,
)
from application.services.below_cost import BelowCostChecker
from domain.entities import Location, Product, Supplier
from domain.enums import AcquisitionSource, DeviceCondition, TrackingType
from domain.permissions import Permission
from domain.value_objects import SKU, Currency, Money
from tests.application.builders import World, make_world

VALID_IMEI = "490154203237518"


@pytest.fixture
def world() -> World:
    return make_world()


def _a_place(world: World) -> Location:
    location = getattr(world, "_accessory_place", None)
    if location is None:
        location = Location(name="Shop", is_active=True, created_at=world.clock.now())
        world.locations.by_id[location.id] = location
        world._accessory_place = location
    return location


def _a_supplier(world: World) -> Supplier:
    supplier = Supplier(
        name="Tashkent Mobile", is_active=True, created_at=world.clock.now()
    )
    world.suppliers.by_id[supplier.id] = supplier
    return supplier


async def make_accessory(
    world: World, sku: str, default_sale_price_minor: int | None
) -> Product:
    price = (
        Money(default_sale_price_minor, Currency.UZS)
        if default_sale_price_minor is not None
        else None
    )
    product = Product(
        sku=SKU.parse(sku),
        name=sku,
        tracking_type=TrackingType.QUANTITY,
        currency=Currency.UZS,
        default_sale_price=price,
        is_active=True,
        created_at=world.clock.now(),
    )
    world.products.by_id[product.id] = product
    return product


async def make_serial_product(
    world: World, sku: str, default_sale_price_minor: int
) -> Product:
    product = Product(
        sku=SKU.parse(sku),
        name=sku,
        tracking_type=TrackingType.SERIAL,
        currency=Currency.USD,
        default_sale_price=Money(default_sale_price_minor, Currency.USD),
        is_active=True,
        created_at=world.clock.now(),
    )
    world.products.by_id[product.id] = product
    return product


async def _confirmed_receipt(world: World, lines: list[ReceiptLine]):
    location = _a_place(world)
    supplier = _a_supplier(world)
    created = await world.create_goods_receipt().handle(
        CreateGoodsReceiptCommand(
            location_id=location.id,
            acquisition_source=AcquisitionSource.SUPPLIER,
            supplier_id=supplier.id,
            lines=lines,
        )
    )
    assert created.data is not None
    return await world.receipts.get(created.data.id)


async def _confirm(world: World, receipt):
    await world.confirm_goods_receipt(None, Permission.COST_VIEW).handle(
        ConfirmGoodsReceiptCommand(goods_receipt_id=receipt.id)
    )
    reloaded = await world.receipts.get(receipt.id)
    assert reloaded is not None
    world.last_receipt = reloaded
    return reloaded


async def receive_accessory(
    world: World, product: Product, quantity: int, unit_cost_minor: int
):
    """A confirmed goods receipt for one QUANTITY line at a fixed location."""
    receipt = await _confirmed_receipt(
        world,
        [
            ReceiptLine(
                product_id=product.id,
                quantity=quantity,
                unit_cost=str(unit_cost_minor),
            )
        ],
    )
    return await _confirm(world, receipt)


async def test_alert_when_new_batch_lifts_average_above_catalog_price(world):
    # accessory priced in the catalog at 10_00
    product = await make_accessory(world, sku="CASE-X", default_sale_price_minor=1000)

    # batch 1: 10 @ 6_00 -> average 6_00, below catalog price, no alert
    await receive_accessory(world, product, quantity=10, unit_cost_minor=600)
    checker = BelowCostChecker(world.products, world.cost_pool_reader)
    receipt1 = world.last_receipt
    assert await checker.alerts_for(receipt1) == []

    # batch 2: 10 @ 14_00 -> pool 20 @ (60_00 + 140_00) = 200_00 -> average 10_00
    receipt2 = await receive_accessory(world, product, quantity=10, unit_cost_minor=1400)
    alerts = await checker.alerts_for(receipt2)
    assert len(alerts) == 1
    assert alerts[0].product_id == product.id
    assert alerts[0].sku == "CASE-X"
    assert alerts[0].catalog_price.amount_minor == 1000
    assert alerts[0].average_unit_cost.amount_minor == 1000  # >= triggers


async def test_no_alert_for_a_product_with_no_catalog_price(world):
    product = await make_accessory(world, sku="NOPRICE", default_sale_price_minor=None)
    receipt = await receive_accessory(world, product, quantity=5, unit_cost_minor=900)
    checker = BelowCostChecker(world.products, world.cost_pool_reader)
    assert await checker.alerts_for(receipt) == []


async def test_serialized_lines_are_out_of_scope(world):
    # SERIAL product catalogued at $5_00, received at a $7_00 acquisition cost:
    # a serialized unit carries its own cost, so the pooled check ignores it.
    product = await make_serial_product(world, sku="IP-1", default_sale_price_minor=500)
    receipt = await _confirmed_receipt(
        world, [ReceiptLine(product_id=product.id, quantity=1)]
    )
    await world.scan_receipt_unit(None, Permission.PRICING_SET).handle(
        ScanReceiptUnitCommand(
            imei=VALID_IMEI,
            goods_receipt_id=receipt.id,
            condition=DeviceCondition.NEW,
            acquisition_cost="700",
            asking_price="700",
        )
    )
    confirmed = await _confirm(world, receipt)

    assert confirmed.lines[0].is_serial is True
    checker = BelowCostChecker(world.products, world.cost_pool_reader)
    assert await checker.alerts_for(confirmed) == []


async def test_confirm_goods_receipt_returns_below_cost_alert(world):
    product = await make_accessory(world, sku="CASE-Z", default_sale_price_minor=1000)
    await receive_accessory(world, product, quantity=10, unit_cost_minor=600)

    receipt = await _confirmed_receipt(
        world, [ReceiptLine(product_id=product.id, quantity=10, unit_cost="1400")]
    )
    result = await world.confirm_goods_receipt(None, Permission.COST_VIEW).handle(
        ConfirmGoodsReceiptCommand(goods_receipt_id=receipt.id)
    )

    assert result.success
    assert result.data is not None
    alerts = result.data.below_cost_alerts
    assert len(alerts) == 1
    assert alerts[0].sku == "CASE-Z"
    assert alerts[0].catalog_price_minor == 1000
    assert alerts[0].average_unit_cost_minor == 1000
    assert result.data.status.value == "confirmed"


async def test_confirm_returns_no_alert_when_below_cost(world):
    product = await make_accessory(world, sku="OK-1", default_sale_price_minor=5000)
    receipt = await _confirmed_receipt(
        world, [ReceiptLine(product_id=product.id, quantity=3, unit_cost="900")]
    )
    result = await world.confirm_goods_receipt(None, Permission.COST_VIEW).handle(
        ConfirmGoodsReceiptCommand(goods_receipt_id=receipt.id)
    )
    assert result.data is not None
    assert result.data.below_cost_alerts == []


class _FakeBelowCostQueries:
    def __init__(self, rows: list[BelowCostRow]) -> None:
        self._rows = rows

    async def list_below_cost(
        self, page, page_size, location_id=None, sort=None
    ):
        start = (page - 1) * page_size
        return self._rows[start : start + page_size], len(self._rows)


async def test_list_below_cost_handler_maps_rows():
    row = BelowCostRow(
        product_id=uuid4(),
        sku="CASE-X",
        product_name="Case X",
        location_id=uuid4(),
        location_name="Main",
        quantity=20,
        catalog_price=Money(1000, Currency.USD),
        average_unit_cost=Money(1100, Currency.USD),
    )
    handler = ListBelowCostHandler(_FakeBelowCostQueries([row]))
    result = await handler.handle(ListBelowCostQuery(page=1, page_size=25))

    assert result.success
    assert result.total_items == 1
    one = result.data[0]
    assert one.sku == "CASE-X"
    assert one.catalog_price_minor == 1000
    assert one.average_unit_cost_minor == 1100
    assert one.shortfall_minor == 100


async def test_two_lines_for_the_same_accessory_yield_one_alert(world):
    product = await make_accessory(world, sku="CASE-Y", default_sale_price_minor=1000)
    receipt = await _confirmed_receipt(
        world,
        [
            ReceiptLine(product_id=product.id, quantity=5, unit_cost="1000"),
            ReceiptLine(product_id=product.id, quantity=5, unit_cost="1200"),
        ],
    )
    confirmed = await _confirm(world, receipt)

    checker = BelowCostChecker(world.products, world.cost_pool_reader)
    alerts = await checker.alerts_for(confirmed)
    assert len(alerts) == 1
    assert alerts[0].product_id == product.id
