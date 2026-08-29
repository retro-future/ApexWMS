"""FR-11.7: a payment settles a debt and never books revenue.

**This suite exists to catch a future handler booking revenue per
instalment.** §11 names double-counting revenue as cash the signature bug
of naive credit systems, and it is invisible when it happens: every figure
looks plausible, the store simply appears to have sold the same phone
three times.

The method is the one FR-11.7 prescribes: compute the same figures twice,
once for a cash sale and once for the same sale paid down over several
instalments, and assert the revenue side is identical. Revenue that moves
when money arrives cannot survive that.
"""

from uuid import uuid4

from application.commands.confirm_sales_invoice import ConfirmSalesInvoiceCommand
from application.commands.record_payment import RecordPaymentCommand
from application.dtos import MoneyEffect, Posting, PostingEntry
from domain.entities import Customer, DeviceUnit, Location, Product
from domain.enums import (
    DeviceCondition,
    DeviceStatus,
    DocumentType,
    MovementType,
    PaymentType,
    TrackingType,
    TransactionType,
)
from domain.value_objects import IMEI, SKU, Currency, Money
from tests.application.builders import World, make_world
from tests.application.test_credit_sales import a_scanned_invoice

PRICE = "600"
DEBT = "7800000"
IMEI_A = "490154203237518"

# Together these come to exactly the debt, which is the point: the store
# ends up holding every som it was owed, and the *revenue* never moved.
INSTALMENTS = ("800000", "2000000", "2000000", "3000000")


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def som(major: str) -> Money:
    return Money.from_major(major, Currency.UZS)


async def a_sale(world: World, *, on_credit: bool):
    """One $600 phone sold, for cash or on the store's own book."""
    location = Location(name="Shop", is_active=True, created_at=world.clock.now())
    world.locations.by_id[location.id] = location
    customer = Customer(full_name="Aziz", is_active=True, created_at=world.clock.now())
    world.customers.by_id[customer.id] = customer

    product = Product(
        sku=SKU.parse("IP15P-256"),
        name="iPhone 15 Pro",
        tracking_type=TrackingType.SERIAL,
        currency=Currency.USD,
        default_sale_price=usd(PRICE),
        is_active=True,
        created_at=world.clock.now(),
    )
    world.products.by_id[product.id] = product

    unit = DeviceUnit(
        imei=IMEI.parse(IMEI_A),
        product_id=product.id,
        status=DeviceStatus.IN_STOCK,
        location_id=location.id,
        acquisition_cost=usd("380"),
        condition=DeviceCondition.NEW,
        created_at=world.clock.now(),
    )
    world.units.by_id[unit.id] = unit
    await world.poster().post(
        Posting(
            document_type=DocumentType.GOODS_RECEIPT,
            document_id=uuid4(),
            entries=[
                PostingEntry(
                    movement_type=MovementType.RECEIPT,
                    product_id=product.id,
                    location_id=location.id,
                    quantity_delta=1,
                    device_unit_id=unit.id,
                    new_status=DeviceStatus.IN_STOCK,
                    new_location_id=location.id,
                    money=[MoneyEffect(TransactionType.PURCHASE, -unit.acquisition_cost)],
                )
            ],
        )
    )

    invoice = await a_scanned_invoice(world, location, customer, IMEI_A)
    assert invoice is not None
    terms = (
        {"payment_type": PaymentType.STORE_CREDIT, "debt": DEBT} if on_credit else {}
    )
    result = await world.confirm_sales_invoice().handle(
        ConfirmSalesInvoiceCommand(sales_invoice_id=invoice.id, **terms)
    )
    assert result.data is not None

    if on_credit:
        for amount in INSTALMENTS:
            await world.record_payment().handle(
                RecordPaymentCommand(sales_invoice_id=invoice.id, amount=amount)
            )
    return result.data.id


class TestRevenueIsBookedOnceAtConfirm:
    async def test_paying_a_sale_down_to_zero_books_its_price_exactly_once(self):
        world = make_world()

        await a_sale(world, on_credit=True)

        totals = await world.transaction_queries.totals_by_type()
        assert totals[(TransactionType.SALE_REVENUE, Currency.USD)] == usd("600")

    async def test_four_instalments_write_four_payments_and_no_revenue(self):
        world = make_world()

        await a_sale(world, on_credit=True)

        revenue_rows = [
            t
            for t in world.transactions.rows
            if t.txn_type is TransactionType.SALE_REVENUE
        ]
        assert len(revenue_rows) == 1
        assert len(world.payments.rows) == len(INSTALMENTS)

    async def test_no_payment_ever_writes_a_revenue_row(self):
        """Structural, not incidental: ``PaymentPoster`` can only emit one
        category, and it is not this one."""
        world = make_world()

        await a_sale(world, on_credit=True)

        for payment in world.payments.rows:
            written = [
                t.txn_type
                for t in world.transactions.rows
                if t.document_id == payment.id
            ]
            assert written == [TransactionType.PAYMENT_RECEIVED]


class TestCreditAndCashEarnTheSame:
    """FR-11.7's method: the same phone, sold two ways, earning identically."""

    async def test_the_revenue_side_is_identical(self):
        cash, credit = make_world(), make_world()
        await a_sale(cash, on_credit=False)
        await a_sale(credit, on_credit=True)

        cash_totals = await cash.transaction_queries.totals_by_type()
        credit_totals = await credit.transaction_queries.totals_by_type()

        earned = (TransactionType.SALE_REVENUE, Currency.USD)
        cost = (TransactionType.COGS, Currency.USD)
        assert cash_totals[earned] == credit_totals[earned] == usd("600")
        assert cash_totals[cost] == credit_totals[cost] == usd("-380")

    async def test_the_margin_is_identical(self):
        cash, credit = make_world(), make_world()
        await a_sale(cash, on_credit=False)
        await a_sale(credit, on_credit=True)

        margins = []
        for world in (cash, credit):
            totals = await world.transaction_queries.totals_by_type()
            margins.append(
                totals[(TransactionType.SALE_REVENUE, Currency.USD)]
                + totals[(TransactionType.COGS, Currency.USD)]
            )

        assert margins[0] == margins[1] == usd("220")

    async def test_only_the_cash_collected_differs(self):
        """The gap the owner is meant to see: what was earned against what
        actually came in (FR-10.5)."""
        cash, credit = make_world(), make_world()
        await a_sale(cash, on_credit=False)
        await a_sale(credit, on_credit=True)

        collected = (TransactionType.PAYMENT_RECEIVED, Currency.UZS)
        assert collected not in await cash.transaction_queries.totals_by_type()
        assert (await credit.transaction_queries.totals_by_type())[collected] == som(DEBT)

    async def test_no_som_revenue_column_appears_for_a_dollar_phone(self):
        """The most visible symptom if a payment ever booked revenue: a
        UZS revenue figure on a store that prices its phones in dollars."""
        world = make_world()

        await a_sale(world, on_credit=True)

        totals = await world.transaction_queries.totals_by_type()
        assert (TransactionType.SALE_REVENUE, Currency.UZS) not in totals
        assert (TransactionType.COGS, Currency.UZS) not in totals
