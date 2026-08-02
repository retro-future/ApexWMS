"""FR-2.14 / PRD §4.5b — how a line's sale price is resolved.

The case worth reading first is
``test_a_used_unit_is_refused_rather_than_quoted_the_new_price``. Everything
else here is bookkeeping around it; that one is the bug the rule exists to
prevent, and §11 rates it High precisely because it is invisible — a
plausible number appears, revenue is booked, and the margin report shows
profit that never existed.

Pure domain: two objects, no database.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.entities import DeviceUnit, Product
from domain.enums import DeviceCondition, DeviceStatus, TrackingType
from domain.errors import PriceNotSetError
from domain.services import resolve_sale_price, resolve_sale_price_or_none
from domain.value_objects import IMEI, SKU, Currency, Money

NOW = datetime(2026, 3, 1, tzinfo=UTC)
IMEI_A = "490154203237518"


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def product(price: str | None = None, tracking: TrackingType = TrackingType.SERIAL) -> Product:
    return Product(
        sku=SKU("IP15P-256"),
        name="iPhone 15 Pro",
        tracking_type=tracking,
        currency=Currency.USD,
        default_sale_price=usd(price) if price is not None else None,
        is_active=True,
        created_at=NOW,
    )


def unit(
    condition: DeviceCondition = DeviceCondition.NEW,
    asking: str | None = None,
    cost: str = "380",
) -> DeviceUnit:
    return DeviceUnit(
        imei=IMEI(IMEI_A),
        product_id=uuid4(),
        status=DeviceStatus.IN_STOCK,
        location_id=uuid4(),
        acquisition_cost=usd(cost),
        asking_price=usd(asking) if asking is not None else None,
        condition=condition,
        created_at=NOW,
    )


class TestTheUnitPriceAlwaysWins:
    @pytest.mark.parametrize(
        "condition",
        [DeviceCondition.NEW, DeviceCondition.REFURBISHED, DeviceCondition.USED],
    )
    def test_step_one_beats_the_catalog_for_every_condition(self, condition):
        """Which is also how a *new* unit gets discounted individually — an
        opened box, a display model — with no separate mechanism."""
        assert resolve_sale_price(unit(condition, asking="520"), product("900")) == usd("520")

    def test_a_unit_price_works_with_no_catalog_price_at_all(self):
        """A model the store only ever trades used is just a catalog row
        with no price. No "used-only product" flag is needed."""
        assert resolve_sale_price(unit(DeviceCondition.USED, asking="400"), product()) == usd(
            "400"
        )


class TestTheCatalogPriceIsInheritedOnlyByNewStock:
    def test_a_new_unit_with_no_price_of_its_own_takes_the_catalog_price(self):
        assert resolve_sale_price(unit(DeviceCondition.NEW), product("900")) == usd("900")

    @pytest.mark.parametrize(
        "condition", [DeviceCondition.USED, DeviceCondition.REFURBISHED]
    )
    def test_a_used_unit_is_refused_rather_than_quoted_the_new_price(self, condition):
        """§11's signature bug, and the test that holds the line against it.

        A used iPhone 15 Pro worth $500, received unpriced, against a
        catalog row holding the *new* price of $900. The correct behaviour
        is a refusal — not $900, and not $0.
        """
        with pytest.raises(PriceNotSetError):
            resolve_sale_price(unit(condition), product("900"))

    def test_pricing_the_used_unit_then_makes_it_sellable(self):
        """FR-2.14's stated test, second half: price it at $500 and the
        line takes $500."""
        assert resolve_sale_price(
            unit(DeviceCondition.USED, asking="500"), product("900")
        ) == usd("500")

    def test_the_refusal_names_the_handset_and_who_can_fix_it(self):
        """FR-4.2b: the Seller who hits this cannot price it themselves
        (§2.1), so the message has to say who can."""
        with pytest.raises(PriceNotSetError) as raised:
            resolve_sale_price(unit(DeviceCondition.USED), product("900"))

        message = str(raised.value)
        assert IMEI_A in message
        assert "used" in message
        assert "Manager" in message


class TestQuantityLinesHaveNoUnitStep:
    def test_an_accessory_resolves_to_the_catalog_price(self):
        case = Product(
            sku=SKU("CASE-CLEAR"),
            name="Clear case",
            tracking_type=TrackingType.QUANTITY,
            currency=Currency.UZS,
            default_sale_price=Money.from_major("50000", Currency.UZS),
            is_active=True,
            created_at=NOW,
        )

        assert resolve_sale_price(None, case) == Money.from_major("50000", Currency.UZS)

    def test_an_accessory_without_a_catalog_price_cannot_be_sold_at_all(self):
        """FR-2.12: there is nowhere else a price could come from, so this
        is refused one step earlier than a serialized line would be."""
        with pytest.raises(PriceNotSetError) as raised:
            resolve_sale_price(None, product(tracking=TrackingType.QUANTITY))

        assert "no per-unit price" in str(raised.value)


class TestAskingWithoutInsisting:
    """The worklist (FR-9.6) and the scan-lookup screen (FR-7.2) exist to
    *show* that a price is missing, so they need the same rule without the
    exception."""

    def test_an_unresolvable_price_is_none_rather_than_a_raise(self):
        assert resolve_sale_price_or_none(unit(DeviceCondition.USED), product("900")) is None

    def test_a_resolvable_price_is_the_same_answer_either_way(self):
        priced = unit(DeviceCondition.USED, asking="400")

        assert resolve_sale_price_or_none(priced, product("900")) == resolve_sale_price(
            priced, product("900")
        )
