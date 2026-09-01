"""Generated SKUs and in-store barcodes (FR-2.1, FR-2.3).

No database: the generator runs against the in-memory fakes.
"""

import pytest

from application.commands.create_product import CreateProductCommand
from application.commands.generate_product_barcode import GenerateProductBarcodeCommand
from application.errors import (
    BarcodeAlreadySetError,
    BarcodeGenerationError,
    NotFoundError,
    SkuGenerationError,
)
from domain.enums import CatalogCodeKind, TrackingType
from domain.errors import BarcodeNotAllowedError
from domain.value_objects import Barcode
from tests.application.builders import make_world


async def create(world, **overrides):
    fields = {"name": "iPhone 15 Pro", "tracking_type": TrackingType.SERIAL}
    return await world.create_product().handle(
        CreateProductCommand(**{**fields, **overrides})
    )


class TestSkuGeneration:
    async def test_a_phone_without_a_sku_gets_a_ph_number(self):
        world = make_world()
        first = await create(world)
        second = await create(world)
        assert [first.data.sku, second.data.sku] == ["PH-000001", "PH-000002"]

    async def test_an_accessory_without_a_sku_gets_an_ac_number(self):
        world = make_world()
        result = await create(
            world, tracking_type=TrackingType.QUANTITY, name="Clear case"
        )
        assert result.data.sku == "AC-000001"

    async def test_the_two_prefixes_count_independently(self):
        world = make_world()
        await create(world)
        acc = await create(world, tracking_type=TrackingType.QUANTITY, name="Case")
        assert acc.data.sku == "AC-000001"

    async def test_a_supplied_sku_is_kept_and_does_not_touch_the_counter(self):
        world = make_world()
        await create(world, sku="MY-OWN-1")
        nxt = await create(world)
        assert nxt.data.sku == "PH-000001"

    async def test_a_blank_sku_is_treated_as_absent(self):
        world = make_world()
        result = await create(world, sku="   ")
        assert result.data.sku == "PH-000001"

    async def test_it_skips_a_number_a_manual_sku_already_took(self):
        world = make_world()
        await create(world, sku="PH-000001")
        result = await create(world)
        assert result.data.sku == "PH-000002"

    async def test_it_gives_up_after_five_collisions(self):
        world = make_world()
        for n in range(1, 6):
            await create(world, sku=f"PH-{n:06d}")
        with pytest.raises(SkuGenerationError):
            await create(world)


class TestBarcodeGeneration:
    async def test_an_accessory_can_be_created_with_a_generated_barcode(self):
        world = make_world()
        result = await create(
            world,
            tracking_type=TrackingType.QUANTITY,
            name="Case",
            generate_barcode=True,
        )
        barcode = result.data.barcode
        assert barcode is not None and barcode.startswith("20")
        assert Barcode(barcode) == Barcode.parse(barcode)

    async def test_an_explicit_barcode_wins_over_the_flag(self):
        world = make_world()
        result = await create(
            world,
            tracking_type=TrackingType.QUANTITY,
            name="Case",
            barcode="4006381333931",
            generate_barcode=True,
        )
        assert result.data.barcode == "4006381333931"
        assert world.catalog_codes.counters.get(CatalogCodeKind.BARCODE) is None

    async def test_generate_barcode_on_a_phone_is_refused(self):
        world = make_world()
        with pytest.raises(BarcodeNotAllowedError):
            await create(world, generate_barcode=True)

    async def test_generating_for_an_existing_accessory(self):
        world = make_world()
        created = await create(
            world, tracking_type=TrackingType.QUANTITY, name="Case"
        )
        result = await world.generate_product_barcode().handle(
            GenerateProductBarcodeCommand(product_id=created.data.id)
        )
        assert result.data.barcode is not None

    async def test_generating_twice_is_refused(self):
        world = make_world()
        created = await create(
            world, tracking_type=TrackingType.QUANTITY, name="Case"
        )
        await world.generate_product_barcode().handle(
            GenerateProductBarcodeCommand(product_id=created.data.id)
        )
        with pytest.raises(BarcodeAlreadySetError):
            await world.generate_product_barcode().handle(
                GenerateProductBarcodeCommand(product_id=created.data.id)
            )

    async def test_generating_for_a_phone_is_refused(self):
        world = make_world()
        created = await create(world)
        with pytest.raises(BarcodeNotAllowedError):
            await world.generate_product_barcode().handle(
                GenerateProductBarcodeCommand(product_id=created.data.id)
            )

    async def test_generating_for_an_unknown_product(self):
        world = make_world()
        with pytest.raises(NotFoundError):
            await world.generate_product_barcode().handle(
                GenerateProductBarcodeCommand(product_id=world.tenant.id)
            )

    async def test_it_gives_up_after_five_collisions(self):
        world = make_world()
        for n in range(1, 6):
            await create(
                world,
                tracking_type=TrackingType.QUANTITY,
                name=f"Case {n}",
                barcode=str(Barcode.from_payload(f"20{n:010d}")),
            )
        with pytest.raises(BarcodeGenerationError):
            await create(
                world,
                tracking_type=TrackingType.QUANTITY,
                name="Case x",
                generate_barcode=True,
            )
