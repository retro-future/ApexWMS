"""Product use cases — FR-2.1, FR-2.3, FR-2.4, FR-2.6.

No database: the handlers run against in-memory fakes (PRD §9 Testing).
"""

import pytest

from application.commands.create_product import CreateProductCommand
from application.commands.update_product import UpdateProductCommand
from application.errors import DuplicateBarcodeError, DuplicateSkuError, NotFoundError
from application.queries.get_product import GetProductQuery
from application.queries.list_products import ListProductsQuery
from application.specs import ProductBySku
from domain.enums import TrackingType
from domain.errors import BarcodeNotAllowedError, InvalidBarcodeError, InvalidMoneyError
from domain.value_objects import Currency
from tests.application.builders import make_world

EAN13 = "4006381333931"
OTHER_EAN13 = "5901234123457"


async def create(world, **overrides):
    fields = {"sku": "IP15P-256", "name": "iPhone 15 Pro", "tracking_type": TrackingType.SERIAL}
    return await world.create_product().handle(
        CreateProductCommand(**{**fields, **overrides})
    )


class TestCreate:
    async def test_a_phone_defaults_to_usd_and_an_accessory_to_som(self):
        """FR-2.6 — the caller named no currency in either case."""
        world = make_world()

        phone = await create(world)
        case = await create(
            world, sku="CASE-CLEAR", name="Clear case", tracking_type=TrackingType.QUANTITY
        )

        assert phone.data.currency is Currency.USD
        assert case.data.currency is Currency.UZS

    async def test_the_default_currency_can_be_overridden_at_creation(self):
        """FR-2.6's second half: a store that buys accessories in dollars
        says so, and only here."""
        world = make_world()

        result = await create(
            world, tracking_type=TrackingType.QUANTITY, sku="CASE-USD", currency=Currency.USD
        )

        assert result.data.currency is Currency.USD

    async def test_the_sku_is_normalized_before_it_is_stored(self):
        world = make_world()

        result = await create(world, sku="  ip15p-256 ")

        assert result.data.sku == "IP15P-256"
        assert await world.products.exists(ProductBySku("IP15P-256"))

    async def test_a_price_is_stored_in_minor_units_of_the_products_currency(self):
        """A som price and a dollar price of the same magnitude are not the
        same integer — the exponent lives on the currency (FR-2.9)."""
        world = make_world()

        phone = await create(world, default_sale_price="600.00")
        case = await create(
            world,
            sku="CASE-CLEAR",
            tracking_type=TrackingType.QUANTITY,
            default_sale_price="50000",
        )

        assert phone.data.default_sale_price.minor == 60_000
        assert case.data.default_sale_price.minor == 50_000

    async def test_a_product_may_be_created_unpriced(self):
        world = make_world()

        result = await create(world)

        assert result.data.default_sale_price is None

    async def test_a_fractional_som_price_is_refused(self):
        """UZS has exponent 0 — there is no half som to store."""
        world = make_world()

        with pytest.raises(InvalidMoneyError):
            await create(
                world, tracking_type=TrackingType.QUANTITY, default_sale_price="50000.50"
            )
        assert world.uow.commits == 0

    async def test_a_duplicate_sku_is_refused_and_writes_no_second_row(self):
        world = make_world()
        await create(world)

        with pytest.raises(DuplicateSkuError):
            await create(world, name="A different phone")

        assert len(world.products.by_id) == 1
        assert world.uow.commits == 1  # only the first create

    async def test_a_duplicate_barcode_is_refused(self):
        world = make_world()
        await create(world, sku="CASE-A", tracking_type=TrackingType.QUANTITY, barcode=EAN13)

        with pytest.raises(DuplicateBarcodeError):
            await create(
                world, sku="CASE-B", tracking_type=TrackingType.QUANTITY, barcode=EAN13
            )

        assert len(world.products.by_id) == 1

    async def test_a_barcode_on_a_serial_product_is_refused(self):
        """FR-2.3: barcodes are for quantity items; a phone has an IMEI."""
        world = make_world()

        with pytest.raises(BarcodeNotAllowedError):
            await create(world, barcode=EAN13)

        assert world.uow.commits == 0

    async def test_a_mistyped_barcode_is_refused(self):
        world = make_world()

        with pytest.raises(InvalidBarcodeError):
            await create(
                world, tracking_type=TrackingType.QUANTITY, barcode="4006381333932"
            )

        assert world.uow.commits == 0


class TestUpdate:
    async def test_the_command_offers_no_way_to_change_tracking_type_or_currency(self):
        """FR-2.1 makes both immutable. Rather than stub a movement check
        that always passes until M3, the fields simply do not exist."""
        assert "tracking_type" not in UpdateProductCommand.model_fields
        assert "currency" not in UpdateProductCommand.model_fields

    async def test_renaming_leaves_everything_else_alone(self):
        world = make_world()
        created = await create(world, default_sale_price="600.00")

        result = await world.update_product().handle(
            UpdateProductCommand(product_id=created.data.id, name="iPhone 15 Pro Max")
        )

        assert result.data.name == "iPhone 15 Pro Max"
        assert result.data.sku == "IP15P-256"
        assert result.data.default_sale_price.minor == 60_000

    async def test_deactivating_preserves_the_row(self):
        """FR-2.4: deactivation stops new movements; it does not delete."""
        world = make_world()
        created = await create(world)

        result = await world.update_product().handle(
            UpdateProductCommand(product_id=created.data.id, is_active=False)
        )

        assert result.data.is_active is False
        assert await world.products.get(created.data.id) is not None

    async def test_an_omitted_nullable_field_is_left_alone(self):
        world = make_world()
        created = await create(
            world, tracking_type=TrackingType.QUANTITY, sku="CASE-A", barcode=EAN13
        )

        result = await world.update_product().handle(
            UpdateProductCommand(product_id=created.data.id, name="Clear case v2")
        )

        assert result.data.barcode == EAN13

    async def test_an_explicit_null_clears_it(self):
        world = make_world()
        created = await create(
            world, tracking_type=TrackingType.QUANTITY, sku="CASE-A", barcode=EAN13
        )

        result = await world.update_product().handle(
            # Passed explicitly, so ``barcode`` lands in ``model_fields_set``
            # and the handler clears it rather than leaving it alone.
            UpdateProductCommand(product_id=created.data.id, barcode=None)
        )

        assert result.data.barcode is None

    async def test_moving_a_barcode_onto_a_serial_product_is_refused(self):
        """The entity's invariants are re-run over the mutated state, so
        FR-2.3 cannot be sidestepped by editing rather than creating."""
        world = make_world()
        created = await create(world)

        with pytest.raises(BarcodeNotAllowedError):
            await world.update_product().handle(
                UpdateProductCommand(product_id=created.data.id, barcode=EAN13)
            )

        assert world.uow.commits == 1  # the create only

    async def test_taking_another_products_barcode_is_refused(self):
        world = make_world()
        await create(world, sku="CASE-A", tracking_type=TrackingType.QUANTITY, barcode=EAN13)
        second = await create(
            world, sku="CASE-B", tracking_type=TrackingType.QUANTITY, barcode=OTHER_EAN13
        )

        with pytest.raises(DuplicateBarcodeError):
            await world.update_product().handle(
                UpdateProductCommand(product_id=second.data.id, barcode=EAN13)
            )

    async def test_keeping_its_own_barcode_is_not_a_duplicate(self):
        world = make_world()
        created = await create(
            world, sku="CASE-A", tracking_type=TrackingType.QUANTITY, barcode=EAN13
        )

        result = await world.update_product().handle(
            UpdateProductCommand(product_id=created.data.id, barcode=EAN13, name="Case A")
        )

        assert result.data.barcode == EAN13

    async def test_an_unknown_product_is_not_found(self):
        world = make_world()

        with pytest.raises(NotFoundError):
            await world.update_product().handle(
                UpdateProductCommand(product_id=world.tenant.id, name="Nope")
            )


class TestRead:
    async def test_get_returns_the_product(self):
        world = make_world()
        created = await create(world)

        result = await world.get_product().handle(
            GetProductQuery(product_id=created.data.id)
        )

        assert result.data.sku == "IP15P-256"

    async def test_get_raises_for_an_unknown_id(self):
        world = make_world()

        with pytest.raises(NotFoundError):
            await world.get_product().handle(GetProductQuery(product_id=world.tenant.id))

    async def test_list_pages_and_reports_the_unpaged_total(self):
        world = make_world()
        for n in range(7):
            await create(world, sku=f"SKU-{n}", name=f"Product {n}")

        page = await world.list_products().handle(ListProductsQuery(page=2, page_size=3))

        assert [p.sku for p in page.data] == ["SKU-3", "SKU-4", "SKU-5"]
        assert page.total_items == 7
        assert page.pages_count == 3
        assert page.page_index == 2

    async def test_list_filters_by_search_across_sku_name_and_brand(self):
        world = make_world()
        await create(world, sku="IP15P-256", name="iPhone 15 Pro", brand="Apple")
        await create(world, sku="SG-S24", name="Galaxy S24", brand="Samsung")

        by_brand = await world.list_products().handle(ListProductsQuery(search="samsung"))
        by_sku = await world.list_products().handle(ListProductsQuery(search="ip15"))

        assert [p.sku for p in by_brand.data] == ["SG-S24"]
        assert [p.sku for p in by_sku.data] == ["IP15P-256"]

    async def test_list_can_show_only_deactivated_products(self):
        """The other half of FR-2.4: history stays reachable."""
        world = make_world()
        created = await create(world)
        await create(world, sku="SG-S24", name="Galaxy S24")
        await world.update_product().handle(
            UpdateProductCommand(product_id=created.data.id, is_active=False)
        )

        retired = await world.list_products().handle(ListProductsQuery(is_active=False))

        assert [p.sku for p in retired.data] == ["IP15P-256"]

    async def test_list_filters_by_tracking_type(self):
        world = make_world()
        await create(world)
        await create(
            world, sku="CASE-A", name="Clear case", tracking_type=TrackingType.QUANTITY
        )

        accessories = await world.list_products().handle(
            ListProductsQuery(tracking_type=TrackingType.QUANTITY)
        )

        assert [p.sku for p in accessories.data] == ["CASE-A"]
