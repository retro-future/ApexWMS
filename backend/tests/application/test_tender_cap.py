"""How much a sale settled at the counter will accept (W9).

A tender has no debt to be capped against, so for a long time it had no cap
at all and a zero too many went in silently. The cap here compares only
against the sale's own total in the same currency, so no rate is involved
and a dollar sale settled in som is left alone.
"""

import pytest

from application.commands.record_payment import RecordPaymentCommand
from domain.enums import TrackingType
from domain.errors import TenderExceedsSaleError
from domain.value_objects import Currency
from tests.application.builders import World, make_world
from tests.application.test_sales_invoice import (
    a_place,
    catalogued,
    confirm,
    in_stock,
    opened,
    scan,
    stocked_accessory,
    uzs,
)

CASE_BARCODE = "4006381333931"


@pytest.fixture
def world() -> World:
    return make_world()


async def a_dollar_sale(world: World):
    """One $600 handset, confirmed and settled at the counter."""
    location = a_place(world)
    product = catalogued(world, price="600")
    unit = await in_stock(world, product, location)
    invoice = await opened(world, location)
    await scan(world, invoice, str(unit.imei))
    await confirm(world, invoice)
    return invoice, location


async def tender(world: World, invoice, amount: str, currency=Currency.UZS):
    return await world.record_payment().handle(
        RecordPaymentCommand(
            sales_invoice_id=invoice.id, amount=amount, currency=currency
        )
    )


class TestTheCapOnASingleCurrencySale:
    async def test_more_dollars_than_the_sale_charges_is_refused(self, world):
        invoice, _ = await a_dollar_sale(world)

        with pytest.raises(TenderExceedsSaleError):
            await tender(world, invoice, "6000", Currency.USD)

    async def test_the_exact_total_goes_through(self, world):
        invoice, _ = await a_dollar_sale(world)

        result = await tender(world, invoice, "600", Currency.USD)

        assert result.data is not None
        assert result.data.tendered[0].minor == 60_000

    async def test_less_than_the_total_goes_through(self, world):
        """Part in dollars and the rest in som is a real way to settle."""
        invoice, _ = await a_dollar_sale(world)

        result = await tender(world, invoice, "300", Currency.USD)

        assert result.data is not None

    async def test_the_other_currency_is_not_capped(self, world):
        """Nothing here knows a rate, so a som figure has no column to
        be compared with."""
        invoice, _ = await a_dollar_sale(world)

        result = await tender(world, invoice, "99000000")

        assert result.data is not None


class TestAMixedSaleIsNotCapped:
    """A dollar handset and a som case on one invoice can be settled
    together in either currency, so neither column means anything."""

    async def test_a_som_tender_over_the_som_line_is_allowed(self, world):
        location = a_place(world)
        phone = catalogued(world, price="600")
        unit = await in_stock(world, phone, location)
        case = catalogued(
            world,
            sku="CASE-1",
            price="50000",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 10, uzs("300000"))
        invoice = await opened(world, location)
        await scan(world, invoice, str(unit.imei))
        await scan(world, invoice, CASE_BARCODE)
        await confirm(world, invoice)

        result = await tender(world, invoice, "7650000")

        assert result.data is not None
        assert result.data.tendered[0].minor == 7_650_000
