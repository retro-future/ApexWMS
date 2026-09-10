"""Per-unit pricing — FR-2.15, FR-2.16, FR-2.17, FR-2.18, FR-2.21, §4.5b.

``DeviceUnit.asking_price`` is *the latest row of*
``device_unit_price_changes``, so every assertion about a price is paired
with one about the log that produced it.

The bulk case is the one worth reading twice: an owner marking down eight
handsets off the ageing report needs the call to be all-or-nothing, or
what they saw and what happened diverge silently.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from application.commands.change_device_unit_condition import (
    ChangeDeviceUnitConditionCommand,
)
from application.commands.reprice_device_unit import RepriceDeviceUnitCommand
from application.commands.reprice_device_units import RepriceDeviceUnitsCommand, UnitPrice
from application.errors import NotFoundError
from application.queries.get_device_unit import GetDeviceUnitQuery
from application.queries.get_device_unit_price_history import (
    GetDeviceUnitPriceHistoryQuery,
)
from domain.entities import DeviceUnit, Product
from domain.enums import DeviceCondition, DeviceStatus, TrackingType
from domain.errors import (
    CurrencyMismatchError,
    InvalidMoneyError,
    UnitNotRepriceableError,
)
from domain.permissions import Permission
from domain.value_objects import IMEI, SKU, Currency, Money
from tests.application.builders import make_world

NOW = datetime(2026, 3, 1, tzinfo=UTC)
# Distinct valid-Luhn IMEIs, so a test can hold several handsets at once.
IMEIS = [
    "490154203237518",
    "356938035643809",
    "352099001761481",
    "013269009999998",
]


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


async def catalogued(world, price: str | None = "900", currency=Currency.USD) -> Product:
    product = Product(
        sku=SKU("IP15P-256"),
        name="iPhone 15 Pro",
        tracking_type=TrackingType.SERIAL,
        currency=currency,
        default_sale_price=Money.from_major(price, currency) if price else None,
        is_active=True,
        created_at=NOW,
    )
    await world.products.add(product)
    return product


async def stocked(world, product, imei=IMEIS[0], **overrides) -> DeviceUnit:
    fields = {
        "imei": IMEI(imei),
        "product_id": product.id,
        "status": DeviceStatus.IN_STOCK,
        "location_id": uuid4(),
        "acquisition_cost": Money.from_major("380", product.currency),
        "condition": DeviceCondition.USED,
        "created_at": NOW,
    }
    unit = DeviceUnit(**{**fields, **overrides})
    await world.units.add(unit)
    return unit


async def reprice(world, unit, price, actor=None, reason=None):
    return await world.reprice_device_unit(actor).handle(
        RepriceDeviceUnitCommand(
            device_unit_id=unit.id, asking_price=price, reason=reason
        )
    )


async def history(world, unit):
    result = await world.get_device_unit_price_history().handle(
        GetDeviceUnitPriceHistoryQuery(device_unit_id=unit.id)
    )
    return result.data


class TestPricingOneHandset:
    async def test_the_first_price_has_no_predecessor(self):
        world = make_world()
        unit = await stocked(world, await catalogued(world))

        await reprice(world, unit, "420")

        rows = await history(world, unit)
        assert len(rows) == 1
        assert rows[0].old_price is None
        assert rows[0].new_price.minor == 42_000

    async def test_two_cuts_leave_three_rows_and_the_latest_price(self):
        """FR-2.15's stated test: price at intake, cut twice, and the unit
        shows the third price with three rows behind it."""
        world = make_world()
        unit = await stocked(world, await catalogued(world))

        await reprice(world, unit, "420")
        await reprice(world, unit, "390")
        result = await reprice(world, unit, "360")

        assert result.data.asking_price.minor == Money.from_major("360", Currency.USD).amount_minor
        rows = await history(world, unit)
        assert [
            (None if r.old_price is None else r.old_price.minor, r.new_price.minor)
            for r in rows
        ] == [
            (None, 42_000),
            (42_000, 39_000),
            (39_000, 36_000),
        ]

    async def test_each_cut_names_who_made_it(self):
        world = make_world()
        unit = await stocked(world, await catalogued(world))
        owner, manager = uuid4(), uuid4()

        await reprice(world, unit, "420", actor=owner)
        await reprice(world, unit, "390", actor=manager)

        rows = await history(world, unit)
        assert [r.user_id for r in rows] == [owner, manager]

    async def test_a_reason_is_recorded_but_never_required(self):
        world = make_world()
        unit = await stocked(world, await catalogued(world))

        await reprice(world, unit, "420")
        await reprice(world, unit, "390", reason="two months on the shelf")

        rows = await history(world, unit)
        assert [r.reason for r in rows] == [None, "two months on the shelf"]

    async def test_repricing_to_the_same_amount_records_nothing(self):
        """The ageing report counts markdowns (FR-9.4); a no-op cut would
        inflate that count with an event that did not happen."""
        world = make_world()
        unit = await stocked(world, await catalogued(world))
        await reprice(world, unit, "420")

        await reprice(world, unit, "420")

        assert len(await history(world, unit)) == 1

    async def test_an_unknown_handset_cannot_be_priced(self):
        world = make_world()

        with pytest.raises(NotFoundError):
            await world.reprice_device_unit().handle(
                RepriceDeviceUnitCommand(device_unit_id=uuid4(), asking_price="420")
            )


class TestWhatRepricingMayNotDo:
    @pytest.mark.parametrize(
        "status",
        [DeviceStatus.SOLD, DeviceStatus.RETURNED_TO_SUPPLIER, DeviceStatus.WRITTEN_OFF],
    )
    async def test_a_handset_that_has_left_cannot_be_repriced(self, status):
        """FR-2.16 — repricing a sold phone is meaningless and would
        corrupt its trace. The error names the status."""
        world = make_world()
        unit = await stocked(
            world, await catalogued(world), status=status, location_id=None
        )

        with pytest.raises(UnitNotRepriceableError) as raised:
            await reprice(world, unit, "420")

        assert status.value in str(raised.value)

    async def test_a_reserved_handset_may_still_be_repriced(self):
        """FR-2.16 allows it on purpose: the open draft holding the unit
        picks the new price up at confirm (FR-4.5b1)."""
        world = make_world()
        unit = await stocked(world, await catalogued(world), status=DeviceStatus.RESERVED)

        result = await reprice(world, unit, "420")

        assert result.data.asking_price is not None

    async def test_a_price_in_another_currency_is_refused(self):
        """FR-2.13: a unit takes its currency from its product, and the
        parser is handed the product's — so a som figure against a USD
        handset is read as dollars, not silently converted. The direct
        service call is what proves the guard itself."""
        world = make_world()
        unit = await stocked(world, await catalogued(world))

        with pytest.raises(CurrencyMismatchError):
            await world.unit_repricer().set_price(
                unit, Money.from_major("5000000", Currency.UZS)
            )

    async def test_a_negative_price_is_refused(self):
        world = make_world()
        unit = await stocked(world, await catalogued(world))

        with pytest.raises(InvalidMoneyError):
            await reprice(world, unit, "-10")

    async def test_repricing_writes_no_money_and_no_movement(self):
        """FR-2.17: a markdown moves no money, so it books nothing — even
        below cost. v1 carries stock at cost, and the loss on a bad buy is
        recognised when the unit sells, not when the sticker changes."""
        world = make_world()
        unit = await stocked(world, await catalogued(world))

        await reprice(world, unit, "300")  # below the $380 it cost

        assert world.transactions.rows == []
        assert world.movements.rows == []
        assert (await world.units.get(unit.id)).acquisition_cost == usd("380")


class TestBulkRepricing:
    async def test_many_units_are_priced_in_one_call(self):
        """FR-2.21: the ageing report hands the owner a list, and pricing
        them one HTTP call at a time is what this route avoids."""
        world = make_world()
        product = await catalogued(world)
        units = [await stocked(world, product, imei=imei) for imei in IMEIS[:3]]

        result = await world.reprice_device_units().handle(
            RepriceDeviceUnitsCommand(
                prices=[
                    UnitPrice(device_unit_id=u.id, asking_price=p)
                    for u, p in zip(units, ("400", "420", "380"), strict=True)
                ],
                reason="Ramadan clearance",
            )
        )

        assert result.data == 3
        assert len(world.unit_price_changes.rows) == 3
        assert {r.reason for r in world.unit_price_changes.rows} == {"Ramadan clearance"}

    async def test_each_unit_keeps_its_own_stated_price(self):
        """No percentage, no formula — §1.3 rejects automated valuation,
        and applying one across a list is still automating it."""
        world = make_world()
        product = await catalogued(world)
        units = [await stocked(world, product, imei=imei) for imei in IMEIS[:3]]

        await world.reprice_device_units().handle(
            RepriceDeviceUnitsCommand(
                prices=[
                    UnitPrice(device_unit_id=u.id, asking_price=p)
                    for u, p in zip(units, ("400", "420", "380"), strict=True)
                ]
            )
        )

        priced = {
            str((await world.units.get(u.id)).asking_price.amount_minor) for u in units
        }
        assert priced == {"40000", "42000", "38000"}

    async def test_one_ineligible_unit_rejects_the_whole_call(self):
        """FR-2.21's stated test: add a SOLD unit to a batch of eight and
        the call is rejected with **nothing** written."""
        world = make_world()
        product = await catalogued(world)
        good = [await stocked(world, product, imei=imei) for imei in IMEIS[:2]]
        sold = await stocked(
            world, product, imei=IMEIS[2], status=DeviceStatus.SOLD, location_id=None
        )

        with pytest.raises(UnitNotRepriceableError):
            await world.reprice_device_units().handle(
                RepriceDeviceUnitsCommand(
                    prices=[
                        UnitPrice(device_unit_id=u.id, asking_price="400")
                        for u in [*good, sold]
                    ]
                )
            )

        assert world.unit_price_changes.rows == []
        assert world.uow.commits == 0

    async def test_an_unknown_unit_rejects_the_whole_call(self):
        world = make_world()
        product = await catalogued(world)
        known = await stocked(world, product)

        with pytest.raises(NotFoundError):
            await world.reprice_device_units().handle(
                RepriceDeviceUnitsCommand(
                    prices=[
                        UnitPrice(device_unit_id=known.id, asking_price="400"),
                        UnitPrice(device_unit_id=uuid4(), asking_price="400"),
                    ]
                )
            )

        assert world.unit_price_changes.rows == []


class TestCondition:
    async def test_flipping_a_new_unit_to_used_makes_it_unsellable(self):
        """FR-2.18's stated test — and the point of the whole rule: the
        unit stops resolving to a price rather than continuing to quote
        the model's *new* price of $900."""
        world = make_world()
        product = await catalogued(world, price="900")
        unit = await stocked(world, product, condition=DeviceCondition.NEW)

        before = await world.get_device_unit().handle(
            GetDeviceUnitQuery(device_unit_id=unit.id)
        )
        assert before.data.resolved_price.minor == 90_000

        await world.change_device_unit_condition().handle(
            ChangeDeviceUnitConditionCommand(
                device_unit_id=unit.id, condition=DeviceCondition.USED
            )
        )

        after = await world.get_device_unit().handle(
            GetDeviceUnitQuery(device_unit_id=unit.id)
        )
        assert after.data.resolved_price is None

    async def test_a_sold_handsets_condition_is_settled(self):
        world = make_world()
        unit = await stocked(
            world,
            await catalogued(world),
            status=DeviceStatus.SOLD,
            location_id=None,
        )

        with pytest.raises(UnitNotRepriceableError):
            await world.change_device_unit_condition().handle(
                ChangeDeviceUnitConditionCommand(
                    device_unit_id=unit.id, condition=DeviceCondition.REFURBISHED
                )
            )


class TestCostVisibility:
    async def test_cost_and_cash_paid_are_absent_without_the_permission(self):
        """FR-1.7: response-shaping, not UI hiding — a Seller never
        receives the figures at all."""
        world = make_world()
        unit = await stocked(
            world,
            await catalogued(world),
            cash_paid_minor=4_200_000,
            cash_paid_currency=Currency.UZS,
        )

        result = await world.get_device_unit().handle(
            GetDeviceUnitQuery(device_unit_id=unit.id)
        )

        assert result.data.acquisition_cost is None
        assert result.data.cash_paid is None

    async def test_a_manager_sees_cost_and_what_was_actually_paid(self):
        """§4.5b: *"paid 4 200 000 so'm · booked at $330"* — the som figure
        beside the booked cost, and in no total anywhere."""
        world = make_world()
        unit = await stocked(
            world,
            await catalogued(world),
            acquisition_cost=usd("330"),
            cash_paid_minor=4_200_000,
            cash_paid_currency=Currency.UZS,
        )

        result = await world.get_device_unit(None, Permission.COST_VIEW).handle(
            GetDeviceUnitQuery(device_unit_id=unit.id)
        )

        assert result.data.acquisition_cost.minor == 33_000
        assert result.data.cash_paid == "4 200 000 so'm"

    async def test_the_resolved_price_is_visible_to_everyone(self):
        """FR-7.2: the price is what the Seller actually needs at the
        counter; the cost is what they must not see."""
        world = make_world()
        unit = await stocked(world, await catalogued(world))
        await reprice(world, unit, "420")

        result = await world.get_device_unit().handle(
            GetDeviceUnitQuery(device_unit_id=unit.id)
        )

        assert result.data.resolved_price.minor == 42_000
        assert result.data.acquisition_cost is None
