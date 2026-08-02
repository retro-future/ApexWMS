"""The catalog-price log — FR-2.19, FR-2.20, FR-9.2b.

``Product.default_sale_price`` is *the latest row of*
``product_price_changes`` (PRD §4.5b), so these tests hold the projection
and the log against each other: every assertion about the price is paired
with one about the history that produced it.

No database: the handlers run against in-memory fakes (PRD §9 Testing).
"""

from uuid import uuid4

import pytest

from application.commands.create_product import CreateProductCommand
from application.commands.update_product import UpdateProductCommand
from application.errors import NotFoundError
from application.queries.get_product_price_history import GetProductPriceHistoryQuery
from domain.enums import TrackingType
from domain.errors import CurrencyMismatchError, InvalidMoneyError, PriceCannotBeUnsetError
from domain.value_objects import Currency, Money
from tests.application.builders import make_world


async def create(world, actor=None, **overrides):
    fields = {"sku": "IP15P-256", "name": "iPhone 15 Pro", "tracking_type": TrackingType.SERIAL}
    return await world.create_product(actor).handle(
        CreateProductCommand(**{**fields, **overrides})
    )


async def reprice(world, product_id, price, actor=None, reason=None):
    return await world.update_product(actor).handle(
        UpdateProductCommand(
            product_id=product_id, default_sale_price=price, price_reason=reason
        )
    )


async def history(world, product_id):
    result = await world.get_product_price_history().handle(
        GetProductPriceHistoryQuery(product_id=product_id)
    )
    return result.data


class TestTheLogStartsWithTheFirstPrice:
    async def test_a_product_created_with_a_price_logs_it_with_no_predecessor(self):
        """FR-2.19: the first row has a null old price. Seeding the field
        directly would leave the opening price the one figure in the
        catalog with no author and no timestamp."""
        world = make_world()

        result = await create(world, default_sale_price="900")

        rows = await history(world, result.data.id)
        assert len(rows) == 1
        assert rows[0].old_price is None
        assert rows[0].new_price_minor == 90_000

    async def test_a_product_created_without_a_price_has_an_empty_log(self):
        """FR-2.12: a SERIAL product with no catalog price is valid — its
        units carry their own. Nothing happened, so nothing is recorded."""
        world = make_world()

        result = await create(world)

        assert result.data.default_sale_price is None
        assert await history(world, result.data.id) == []

    async def test_the_first_price_names_whoever_set_it(self):
        world = make_world()
        owner = uuid4()

        result = await create(world, actor=owner, default_sale_price="900")

        rows = await history(world, result.data.id)
        assert rows[0].user_id == owner


class TestRepricing:
    async def test_two_cuts_leave_three_rows_and_the_latest_price(self):
        """FR-2.19's stated test: $900 → $850 → $780."""
        world = make_world()
        product = (await create(world, default_sale_price="900")).data

        await reprice(world, product.id, "850")
        result = await reprice(world, product.id, "780")

        assert result.data.default_sale_price_minor == 78_000
        rows = await history(world, product.id)
        assert [(r.old_price_minor, r.new_price_minor) for r in rows] == [
            (None, 90_000),
            (90_000, 85_000),
            (85_000, 78_000),
        ]

    async def test_the_projection_is_always_the_last_row(self):
        world = make_world()
        product = (await create(world, default_sale_price="900")).data

        result = await reprice(world, product.id, "780")

        latest = await world.price_changes.latest_for_product(product.id)
        assert latest is not None
        assert latest.new_price.amount_minor == result.data.default_sale_price_minor

    async def test_a_product_that_had_no_price_can_be_given_one(self):
        """FR-2.19 — "including being set on a product that had none"."""
        world = make_world()
        product = (await create(world)).data

        result = await reprice(world, product.id, "780")

        assert result.data.default_sale_price_minor == 78_000
        rows = await history(world, product.id)
        assert len(rows) == 1 and rows[0].old_price is None

    async def test_a_reason_is_recorded_when_one_is_given(self):
        world = make_world()
        product = (await create(world, default_sale_price="900")).data

        await reprice(world, product.id, "780", reason="iPhone 16 shipped")

        rows = await history(world, product.id)
        assert rows[-1].reason == "iPhone 16 shipped"

    async def test_a_reason_is_never_required(self):
        world = make_world()
        product = (await create(world, default_sale_price="900")).data

        await reprice(world, product.id, "780")

        rows = await history(world, product.id)
        assert rows[-1].reason is None

    async def test_repricing_to_the_same_amount_records_nothing(self):
        """A model repriced to what it already costs is not an event, and
        logging it would put noise into the one report meant to answer
        "when did this move?"."""
        world = make_world()
        product = (await create(world, default_sale_price="900")).data

        await reprice(world, product.id, "900")

        assert len(await history(world, product.id)) == 1

    async def test_an_untouched_price_survives_an_unrelated_edit(self):
        """A rename is not a price change and must not log one."""
        world = make_world()
        product = (await create(world, default_sale_price="900")).data

        result = await world.update_product().handle(
            UpdateProductCommand(product_id=product.id, name="iPhone 15 Pro (256GB)")
        )

        assert result.data.default_sale_price_minor == 90_000
        assert len(await history(world, product.id)) == 1


class TestWhatARepricingMayNotDo:
    async def test_a_price_cannot_be_cleared_once_set(self):
        """The log has no row shape meaning "no longer priced", so clearing
        the field would leave the projection contradicting its own history.
        A model the store has stopped selling is deactivated instead."""
        world = make_world()
        product = (await create(world, default_sale_price="900")).data

        with pytest.raises(PriceCannotBeUnsetError):
            await reprice(world, product.id, None)

    async def test_clearing_a_price_that_was_never_set_is_harmless(self):
        world = make_world()
        product = (await create(world)).data

        result = await reprice(world, product.id, None)

        assert result.data.default_sale_price is None
        assert await history(world, product.id) == []

    async def test_a_price_cannot_be_negative(self):
        world = make_world()
        product = (await create(world, default_sale_price="900")).data

        with pytest.raises(InvalidMoneyError):
            await reprice(world, product.id, "-10")

    async def test_a_fractional_som_price_is_refused(self):
        """UZS has exponent 0 — there is no half a som (PRD §4.5)."""
        world = make_world()
        product = (
            await create(
                world,
                sku="CASE-CLEAR",
                name="Clear case",
                tracking_type=TrackingType.QUANTITY,
                default_sale_price="50000",
            )
        ).data

        with pytest.raises(InvalidMoneyError):
            await reprice(world, product.id, "50000.5")

    async def test_the_currency_of_a_log_row_cannot_diverge_from_its_predecessor(self):
        """FR-2.19's second half, at the level the entity can enforce it:
        a product's currency is immutable (FR-2.1), so a repricing is
        always a new amount in the currency it already had."""
        from domain.entities import ProductPriceChange

        with pytest.raises(CurrencyMismatchError):
            ProductPriceChange(
                product_id=uuid4(),
                occurred_at=make_world().clock.now(),
                old_price=Money.from_major("900", Currency.USD),
                new_price=Money.from_major("11000000", Currency.UZS),
                user_id=uuid4(),
            )


class TestReadingTheHistory:
    async def test_an_unknown_product_is_not_an_empty_history(self):
        """FR-9.2b answers a question about a product; "this model has never
        been repriced" and "there is no such model" are different answers."""
        world = make_world()

        with pytest.raises(NotFoundError):
            await history(world, uuid4())

    async def test_the_history_is_oldest_first(self):
        world = make_world()
        product = (await create(world, default_sale_price="900")).data
        await reprice(world, product.id, "850")
        await reprice(world, product.id, "780")

        rows = await history(world, product.id)

        assert [r.new_price_minor for r in rows] == [90_000, 85_000, 78_000]

    async def test_one_products_history_never_contains_another_s(self):
        world = make_world()
        phone = (await create(world, default_sale_price="900")).data
        case = (
            await create(
                world,
                sku="CASE-CLEAR",
                name="Clear case",
                tracking_type=TrackingType.QUANTITY,
                default_sale_price="50000",
            )
        ).data

        rows = await history(world, case.id)

        assert [r.new_price_minor for r in rows] == [50_000]
        assert rows[0].currency is Currency.UZS
        assert (await history(world, phone.id))[0].currency is Currency.USD
