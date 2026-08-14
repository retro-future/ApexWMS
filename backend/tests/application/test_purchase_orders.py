"""Purchase orders — PRD §5.3, FR-3.1, FR-3.2, FR-3.9.

The one document whose confirm writes nothing to either ledger, and the
one place M4 answers "how much of what we ordered has actually turned up?"
"""

from uuid import uuid4

import pytest

from application.commands.cancel_purchase_order import CancelPurchaseOrderCommand
from application.commands.confirm_goods_receipt import ConfirmGoodsReceiptCommand
from application.commands.confirm_purchase_order import ConfirmPurchaseOrderCommand
from application.commands.create_goods_receipt import (
    CreateGoodsReceiptCommand,
    ReceiptLine,
)
from application.commands.create_purchase_order import (
    CreatePurchaseOrderCommand,
    OrderLine,
)
from application.commands.scan_receipt_unit import ScanReceiptUnitCommand
from application.errors import NotFoundError
from application.models import Fulfilment
from application.queries.get_purchase_order import GetPurchaseOrderQuery
from domain.entities import Location, Product, Supplier
from domain.enums import AcquisitionSource, DocumentStatus, TrackingType
from domain.errors import DocumentNotConfirmedError, DocumentNotDraftError, OverReceiptError
from domain.permissions import Permission
from domain.value_objects import SKU, Currency, Money
from tests.application.builders import World, make_world

IMEIS = ["490154203237518", "356938035643809", "352099001761481"]


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


def a_supplier(world: World) -> Supplier:
    supplier = Supplier(name="Tashkent Mobile", is_active=True, created_at=world.clock.now())
    world.suppliers.by_id[supplier.id] = supplier
    return supplier


def a_place(world: World) -> Location:
    location = Location(name="Shop", is_active=True, created_at=world.clock.now())
    world.locations.by_id[location.id] = location
    return location


async def ordered(world: World, lines: list[OrderLine], supplier: Supplier | None = None):
    supplier = supplier or a_supplier(world)
    result = await world.create_purchase_order().handle(
        CreatePurchaseOrderCommand(supplier_id=supplier.id, lines=lines)
    )
    assert result.data is not None
    order = await world.orders.get(result.data.id)
    assert order is not None
    return order, supplier


class TestRaisingAnOrder:
    async def test_it_is_a_draft_with_a_number(self):
        world = make_world()
        product = catalogued(world)

        order, _ = await ordered(
            world, [OrderLine(product_id=product.id, quantity=10, unit_cost="700")]
        )

        assert order.status is DocumentStatus.DRAFT
        assert order.number == "PO-2026-0001"
        assert order.lines[0].unit_cost == usd("700")

    async def test_a_line_takes_its_currency_from_its_product(self):
        """FR-2.7: one order, two currencies, and no combined total."""
        world = make_world()
        phone = catalogued(world)
        case = catalogued(world, "CASE-1", TrackingType.QUANTITY, Currency.UZS)

        order, _ = await ordered(
            world,
            [
                OrderLine(product_id=phone.id, quantity=1, unit_cost="600"),
                OrderLine(product_id=case.id, quantity=5, unit_cost="10000"),
            ],
        )

        assert order.subtotals() == {Currency.USD: usd("600"), Currency.UZS: uzs("50000")}

    async def test_an_unknown_supplier_is_refused(self):
        world = make_world()
        product = catalogued(world)

        with pytest.raises(NotFoundError, match="supplier"):
            await world.create_purchase_order().handle(
                CreatePurchaseOrderCommand(
                    supplier_id=uuid4(),
                    lines=[OrderLine(product_id=product.id, quantity=1, unit_cost="700")],
                )
            )

    async def test_an_unknown_product_is_refused(self):
        world = make_world()
        supplier = a_supplier(world)

        with pytest.raises(NotFoundError, match="product"):
            await world.create_purchase_order().handle(
                CreatePurchaseOrderCommand(
                    supplier_id=supplier.id,
                    lines=[OrderLine(product_id=uuid4(), quantity=1, unit_cost="700")],
                )
            )


class TestConfirmingMovesNothing:
    async def test_it_writes_to_neither_ledger(self):
        """FR-3.2: a PO is an intention to buy, not a stock event."""
        world = make_world()
        product = catalogued(world)
        order, _ = await ordered(
            world, [OrderLine(product_id=product.id, quantity=10, unit_cost="700")]
        )

        await world.confirm_purchase_order().handle(
            ConfirmPurchaseOrderCommand(purchase_order_id=order.id)
        )

        assert world.movements.rows == []
        assert world.transactions.rows == []
        reloaded = await world.orders.get(order.id)
        assert reloaded is not None and reloaded.status is DocumentStatus.CONFIRMED

    async def test_a_confirmed_order_cannot_be_confirmed_again(self):
        world = make_world()
        product = catalogued(world)
        order, _ = await ordered(
            world, [OrderLine(product_id=product.id, quantity=1, unit_cost="700")]
        )
        handler = world.confirm_purchase_order()
        await handler.handle(ConfirmPurchaseOrderCommand(purchase_order_id=order.id))

        with pytest.raises(DocumentNotDraftError):
            await handler.handle(ConfirmPurchaseOrderCommand(purchase_order_id=order.id))

    async def test_a_draft_cannot_be_cancelled(self):
        world = make_world()
        product = catalogued(world)
        order, _ = await ordered(
            world, [OrderLine(product_id=product.id, quantity=1, unit_cost="700")]
        )

        with pytest.raises(DocumentNotConfirmedError):
            await world.cancel_purchase_order().handle(
                CancelPurchaseOrderCommand(purchase_order_id=order.id)
            )

    async def test_cancelling_records_why(self):
        world = make_world()
        product = catalogued(world)
        order, _ = await ordered(
            world, [OrderLine(product_id=product.id, quantity=1, unit_cost="700")]
        )
        await world.confirm_purchase_order().handle(
            ConfirmPurchaseOrderCommand(purchase_order_id=order.id)
        )

        await world.cancel_purchase_order().handle(
            CancelPurchaseOrderCommand(
                purchase_order_id=order.id, reason="supplier could not source them"
            )
        )

        reloaded = await world.orders.get(order.id)
        assert reloaded is not None
        assert reloaded.status is DocumentStatus.CANCELLED
        assert reloaded.cancellation_reason == "supplier could not source them"


class TestReceivedVersusOrdered:
    """FR-3.9: pending, partial, complete."""

    async def test_an_untouched_order_is_pending(self):
        world = make_world()
        product = catalogued(world)
        order, _ = await ordered(
            world, [OrderLine(product_id=product.id, quantity=3, unit_cost="700")]
        )

        seen = await world.get_purchase_order().handle(
            GetPurchaseOrderQuery(purchase_order_id=order.id)
        )

        assert seen.data is not None
        assert seen.data.fulfilment is Fulfilment.PENDING
        assert seen.data.lines[0].received_quantity == 0

    async def test_a_draft_receipt_has_received_nothing(self):
        """The goods are still on the van."""
        world = make_world()
        product = catalogued(world)
        order, supplier = await ordered(
            world, [OrderLine(product_id=product.id, quantity=3, unit_cost="700")]
        )
        await world.confirm_purchase_order().handle(
            ConfirmPurchaseOrderCommand(purchase_order_id=order.id)
        )
        await world.create_goods_receipt().handle(
            CreateGoodsReceiptCommand(
                location_id=a_place(world).id,
                supplier_id=supplier.id,
                purchase_order_id=order.id,
            )
        )

        seen = await world.get_purchase_order().handle(
            GetPurchaseOrderQuery(purchase_order_id=order.id)
        )

        assert seen.data is not None
        assert seen.data.fulfilment is Fulfilment.PENDING

    async def test_a_short_delivery_is_partial_and_a_full_one_is_complete(self):
        world = make_world()
        product = catalogued(world)
        location = a_place(world)
        order, supplier = await ordered(
            world, [OrderLine(product_id=product.id, quantity=3, unit_cost="700")]
        )
        await world.confirm_purchase_order().handle(
            ConfirmPurchaseOrderCommand(purchase_order_id=order.id)
        )

        await self._receive(world, order, supplier, location, [IMEIS[0], IMEIS[1]], 2)
        seen = await world.get_purchase_order().handle(
            GetPurchaseOrderQuery(purchase_order_id=order.id)
        )
        assert seen.data is not None
        assert seen.data.fulfilment is Fulfilment.PARTIAL
        assert seen.data.lines[0].received_quantity == 2

        await self._receive(world, order, supplier, location, [IMEIS[2]], 1)
        seen = await world.get_purchase_order().handle(
            GetPurchaseOrderQuery(purchase_order_id=order.id)
        )
        assert seen.data is not None
        assert seen.data.fulfilment is Fulfilment.COMPLETE
        assert seen.data.lines[0].received_quantity == 3

    async def test_an_explicit_line_pushing_past_the_order_is_refused(self):
        world = make_world()
        product = catalogued(world)
        location = a_place(world)
        order, supplier = await ordered(
            world, [OrderLine(product_id=product.id, quantity=3, unit_cost="700")]
        )
        await world.confirm_purchase_order().handle(
            ConfirmPurchaseOrderCommand(purchase_order_id=order.id)
        )
        await self._receive(world, order, supplier, location, [IMEIS[0], IMEIS[1]], 2)

        with pytest.raises(OverReceiptError):
            await world.create_goods_receipt().handle(
                CreateGoodsReceiptCommand(
                    location_id=location.id,
                    supplier_id=supplier.id,
                    purchase_order_id=order.id,
                    lines=[ReceiptLine(product_id=product.id, quantity=2)],
                )
            )

    async def test_a_fully_received_order_has_nothing_left_to_prefill(self):
        world = make_world()
        product = catalogued(world)
        location = a_place(world)
        order, supplier = await ordered(
            world, [OrderLine(product_id=product.id, quantity=3, unit_cost="700")]
        )
        await world.confirm_purchase_order().handle(
            ConfirmPurchaseOrderCommand(purchase_order_id=order.id)
        )
        await self._receive(world, order, supplier, location, [IMEIS[0], IMEIS[1]], 2)
        await self._receive(world, order, supplier, location, [IMEIS[2]], 1)

        with pytest.raises(OverReceiptError):
            await world.create_goods_receipt().handle(
                CreateGoodsReceiptCommand(
                    location_id=location.id,
                    supplier_id=supplier.id,
                    purchase_order_id=order.id,
                )
            )

    async def test_a_second_receipt_prefills_only_what_remains(self):
        world = make_world()
        product = catalogued(world)
        location = a_place(world)
        order, supplier = await ordered(
            world, [OrderLine(product_id=product.id, quantity=3, unit_cost="700")]
        )
        await world.confirm_purchase_order().handle(
            ConfirmPurchaseOrderCommand(purchase_order_id=order.id)
        )
        await self._receive(world, order, supplier, location, [IMEIS[0], IMEIS[1]], 2)

        created = await world.create_goods_receipt().handle(
            CreateGoodsReceiptCommand(
                location_id=location.id,
                supplier_id=supplier.id,
                purchase_order_id=order.id,
            )
        )

        assert created.data is not None
        receipt = await world.receipts.get(created.data.id)
        assert receipt is not None
        assert [(line.product_id, line.quantity) for line in receipt.lines] == [
            (product.id, 1)
        ]

    async def test_a_receipt_raised_from_an_order_prefills_its_lines(self):
        """FR-3.3, and it is always from that order's supplier (FR-3.3b)."""
        world = make_world()
        product = catalogued(world)
        order, supplier = await ordered(
            world, [OrderLine(product_id=product.id, quantity=3, unit_cost="700")]
        )
        await world.confirm_purchase_order().handle(
            ConfirmPurchaseOrderCommand(purchase_order_id=order.id)
        )

        created = await world.create_goods_receipt().handle(
            CreateGoodsReceiptCommand(
                location_id=a_place(world).id,
                acquisition_source=AcquisitionSource.TRADE_IN,
                purchase_order_id=order.id,
            )
        )

        assert created.data is not None
        receipt = await world.receipts.get(created.data.id)
        assert receipt is not None
        assert receipt.acquisition_source is AcquisitionSource.SUPPLIER
        assert receipt.supplier_id == supplier.id
        assert [(line.product_id, line.quantity) for line in receipt.lines] == [
            (product.id, 3)
        ]

    @staticmethod
    async def _receive(world, order, supplier, location, imeis, quantity):
        created = await world.create_goods_receipt().handle(
            CreateGoodsReceiptCommand(
                location_id=location.id,
                supplier_id=supplier.id,
                purchase_order_id=order.id,
                lines=[ReceiptLine(product_id=order.lines[0].product_id, quantity=quantity)],
            )
        )
        assert created.data is not None
        for imei in imeis:
            await world.scan_receipt_unit(None, Permission.PRICING_SET).handle(
                ScanReceiptUnitCommand(
                    imei=imei, goods_receipt_id=created.data.id, acquisition_cost="700"
                )
            )
        await world.confirm_goods_receipt(None, Permission.COST_VIEW).handle(
            ConfirmGoodsReceiptCommand(goods_receipt_id=created.data.id)
        )
