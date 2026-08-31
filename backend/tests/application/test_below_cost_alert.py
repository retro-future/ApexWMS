"""BelowCostChecker — accessories whose weighted-average cost has caught up
to their catalog price (FR-2.15)."""

import pytest

from application.commands.confirm_goods_receipt import ConfirmGoodsReceiptCommand
from application.commands.create_goods_receipt import (
    CreateGoodsReceiptCommand,
    ReceiptLine,
)
from application.services.below_cost import BelowCostChecker
from domain.entities import Location, Product, Supplier
from domain.enums import AcquisitionSource, TrackingType
from domain.permissions import Permission
from domain.value_objects import SKU, Currency, Money
from tests.application.builders import World, make_world


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


async def receive_accessory(
    world: World, product: Product, quantity: int, unit_cost_minor: int
):
    """A confirmed goods receipt for one QUANTITY line at a fixed location."""
    location = _a_place(world)
    supplier = _a_supplier(world)
    created = await world.create_goods_receipt().handle(
        CreateGoodsReceiptCommand(
            location_id=location.id,
            acquisition_source=AcquisitionSource.SUPPLIER,
            supplier_id=supplier.id,
            lines=[
                ReceiptLine(
                    product_id=product.id,
                    quantity=quantity,
                    unit_cost=str(unit_cost_minor),
                )
            ],
        )
    )
    assert created.data is not None
    receipt = await world.receipts.get(created.data.id)
    assert receipt is not None
    await world.confirm_goods_receipt(None, Permission.COST_VIEW).handle(
        ConfirmGoodsReceiptCommand(goods_receipt_id=receipt.id)
    )
    reloaded = await world.receipts.get(receipt.id)
    assert reloaded is not None
    world.last_receipt = reloaded
    return reloaded


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


async def test_no_alert_for_serialized_lines_or_unpriced_products(world):
    product = await make_accessory(world, sku="NOPRICE", default_sale_price_minor=None)
    receipt = await receive_accessory(world, product, quantity=5, unit_cost_minor=900)
    checker = BelowCostChecker(world.products, world.cost_pool_reader)
    assert await checker.alerts_for(receipt) == []
