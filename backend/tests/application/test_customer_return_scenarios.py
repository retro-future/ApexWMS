"""Customer returns as they land in the reports a store actually reads.

``test_customer_returns.py`` pins the ledger. These pin what the sales
summary (FR-9.3) shows once goods come back: the refund is a figure of its
own next to revenue, the margin nets it, and a returned handset keeps the
condition it was sold at (FR-4.9f, FR-2.18).
"""

from application.commands.cancel_customer_return import CancelCustomerReturnCommand
from application.commands.confirm_customer_return import ConfirmCustomerReturnCommand
from application.commands.scan_customer_return_line import ScanCustomerReturnLineCommand
from application.queries.get_sales_summary import GetSalesSummaryQuery
from domain.enums import (
    DeviceCondition,
    DeviceStatus,
    TrackingType,
    TransactionType,
)
from domain.value_objects import Currency
from tests.application.builders import World, make_world
from tests.application.test_customer_returns import booked, opened_return, sold, usd
from tests.application.test_sales_invoice import (
    CASE_BARCODE,
    PHONE_IMEI,
    a_place,
    catalogued,
    in_stock,
    stocked_accessory,
    uzs,
)


def one(subtotals) -> int:
    assert len(subtotals) == 1, subtotals
    return subtotals[0].minor


async def a_cased_sale(world: World, *, units: int, cost: str):
    """``units`` cases sold on one invoice, bought at ``cost`` the lot."""
    location = a_place(world)
    case = catalogued(
        world,
        sku="CASE-BLK",
        price="50000",
        tracking=TrackingType.QUANTITY,
        currency=Currency.UZS,
        barcode=CASE_BARCODE,
    )
    await stocked_accessory(world, case, location, units, uzs(cost))
    invoice = await sold(world, location, codes=(CASE_BARCODE,) * units)
    return location, invoice


async def scan_n(world: World, document, code: str, n: int) -> None:
    for _ in range(n):
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(code=code, customer_return_id=document.id)
        )


async def summary(world: World):
    result = await world.get_sales_summary().handle(GetSalesSummaryQuery())
    assert result.data is not None
    return result.data


class TestAPartialReturnShowsUpInTheMoneyView:
    async def test_the_refund_is_its_own_figure_and_the_margin_nets_it(self):
        world = make_world()
        # 5 cases in at 100 000 the lot (20 000 each), sold at 50 000 each.
        location, invoice = await a_cased_sale(world, units=5, cost="100000")

        document = await opened_return(world, invoice, location)
        await scan_n(world, document, CASE_BARCODE, 2)
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=document.id)
        )

        total = (await summary(world)).total
        assert one(total.revenue) == 250_000
        assert one(total.returns) == -100_000
        assert one(total.cost_of_goods) == -60_000  # -100 000 + 40 000 back
        assert one(total.margin) == 90_000

    async def test_a_return_does_not_lower_the_units_sold_count(self):
        world = make_world()
        location, invoice = await a_cased_sale(world, units=5, cost="100000")
        document = await opened_return(world, invoice, location)
        await scan_n(world, document, CASE_BARCODE, 2)
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=document.id)
        )

        assert (await summary(world)).total.units_sold == 5

    async def test_cancelling_the_return_takes_it_back_out(self):
        world = make_world()
        location, invoice = await a_cased_sale(world, units=3, cost="90000")
        document = await opened_return(world, invoice, location)
        await scan_n(world, document, CASE_BARCODE, 1)
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=document.id)
        )
        await world.cancel_customer_return().handle(
            CancelCustomerReturnCommand(customer_return_id=document.id, reason="mistake")
        )

        total = (await summary(world)).total
        assert booked(world, TransactionType.SALES_RETURN_REFUND, Currency.UZS).is_zero
        assert one(total.margin) == one(total.revenue) + one(total.cost_of_goods)


class TestTwoCurrenciesStayApart:
    async def test_a_som_refund_never_touches_the_dollar_column(self):
        world = make_world()
        location = a_place(world)
        phone = catalogued(world, price="900")
        await in_stock(world, phone, location, cost="380")
        case = catalogued(
            world,
            sku="CASE-BLK",
            price="50000",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 3, uzs("90000"))
        invoice = await sold(world, location, codes=(PHONE_IMEI, *([CASE_BARCODE] * 3)))

        document = await opened_return(world, invoice, location)
        await scan_n(world, document, CASE_BARCODE, 1)
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=document.id)
        )

        total = (await summary(world)).total
        returns = {s.currency: s.minor for s in total.returns}
        assert returns == {Currency.UZS: -50_000}


class TestAReturnedNewHandsetIsStillNew:
    """FR-4.9f + FR-2.18: condition is set at intake, changed only by hand."""

    async def test_it_comes_back_new_and_can_be_sold_again(self):
        world = make_world()
        location = a_place(world)
        phone = catalogued(world, price="900")
        unit = await in_stock(
            world, phone, location, cost="380", condition=DeviceCondition.NEW
        )
        first = await sold(world, location)

        document = await opened_return(world, first, location)
        await scan_n(world, document, PHONE_IMEI, 1)
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=document.id)
        )

        back = await world.units.get(unit.id)
        assert back is not None
        assert back.condition is DeviceCondition.NEW
        assert back.status is DeviceStatus.IN_STOCK

        await sold(world, location)
        assert booked(world, TransactionType.SALE_REVENUE, Currency.USD) == usd("1800")
