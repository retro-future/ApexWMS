"""Customer returns end to end through the handlers — PRD §5.4b, FR-4.9.

No database: the whole flow runs against the in-memory fakes. What these
cover that the domain tests cannot is everything needing a lookup — that
the handset is still sold and was sold on *this* invoice, what the sale
carried the goods at, the two ledgers, and the som debt a return relieves.

The figure most worth pinning down is the cost coming back. A return books
``COGS`` **positive** at what the sale booked, which is what puts a returned
accessory back into the weighted-average pool at the value it left. Read it
from the current pool instead and the goods re-enter at a price nobody ever
paid for them.
"""

from uuid import uuid4

import pytest

from application.commands.cancel_customer_return import CancelCustomerReturnCommand
from application.commands.cancel_sales_invoice import CancelSalesInvoiceCommand
from application.commands.confirm_customer_return import ConfirmCustomerReturnCommand
from application.commands.confirm_sales_invoice import ConfirmSalesInvoiceCommand
from application.commands.create_customer_return import CreateCustomerReturnCommand
from application.commands.create_sales_invoice import CreateSalesInvoiceCommand
from application.commands.record_payment import RecordPaymentCommand
from application.commands.scan_customer_return_line import ScanCustomerReturnLineCommand
from application.commands.scan_invoice_line import ScanInvoiceLineCommand
from application.commands.set_customer_return_refund import (
    SetCustomerReturnRefundCommand,
)
from application.commands.unscan_customer_return_line import (
    UnscanCustomerReturnLineCommand,
)
from application.queries.get_sales_invoice import GetSalesInvoiceQuery
from domain.entities import Customer
from domain.enums import (
    CustomerReturnReason,
    DeviceStatus,
    DocumentStatus,
    DocumentType,
    MovementType,
    PaymentType,
    TrackingType,
    TransactionType,
)
from domain.errors import (
    AlreadyReturnedError,
    DebtReliefError,
    DocumentNotConfirmedError,
    InvoiceHasReturnsError,
    OverpaymentError,
    RefundExceedsChargeError,
    UnapprovedRefundError,
    UnitNotReturnableError,
)
from domain.value_objects import Currency, Money
from tests.application.builders import World, make_world
from tests.application.test_sales_invoice import (
    CASE_BARCODE,
    OTHER_IMEI,
    PHONE_IMEI,
    a_place,
    catalogued,
    in_stock,
    stocked_accessory,
    usd,
    uzs,
)


def a_customer(world: World, name: str = "Aziz") -> Customer:
    customer = Customer(full_name=name, is_active=True, created_at=world.clock.now())
    world.customers.by_id[customer.id] = customer
    return customer


async def sold(
    world: World,
    location,
    *,
    codes: tuple[str, ...] = (PHONE_IMEI,),
    customer: Customer | None = None,
    payment_type: PaymentType = PaymentType.PAID_IN_FULL,
    debt: str | None = None,
    down: str | None = None,
):
    """A confirmed sale, which is the only thing a return may name."""
    result = await world.create_sales_invoice().handle(
        CreateSalesInvoiceCommand(
            location_id=location.id,
            customer_id=None if customer is None else customer.id,
        )
    )
    assert result.data is not None
    invoice_id = result.data.id
    for code in codes:
        await world.scan_invoice_line().handle(
            ScanInvoiceLineCommand(code=code, sales_invoice_id=invoice_id)
        )
    confirmed = await world.confirm_sales_invoice().handle(
        ConfirmSalesInvoiceCommand(
            sales_invoice_id=invoice_id,
            payment_type=payment_type,
            debt=debt,
            down_payment=down,
        )
    )
    assert confirmed.data is not None
    return confirmed.data


async def opened_return(world: World, invoice, location, **overrides):
    result = await world.create_customer_return().handle(
        CreateCustomerReturnCommand(
            sales_invoice_id=invoice.id,
            location_id=location.id,
            reason=CustomerReturnReason.DEFECTIVE,
            **overrides,
        )
    )
    assert result.data is not None
    return result.data


def booked(world: World, txn_type: TransactionType, currency: Currency) -> Money:
    total = Money.zero(currency)
    for txn in world.transactions.rows:
        if txn.txn_type is txn_type and txn.amount.currency is currency:
            total = total + txn.amount
    return total


def movements_of(world: World, unit_id):
    return [m for m in world.movements.rows if m.device_unit_id == unit_id]


class TestReturningAPhoneAtFullPrice:
    """The §5.4b demo: a $520 phone bought at $380 comes back whole."""

    async def _sale(self, world: World):
        location = a_place(world)
        product = catalogued(world, price="520")
        unit = await in_stock(world, product, location, cost="380")
        invoice = await sold(world, location)
        return location, product, unit, invoice

    async def test_the_goods_come_back_and_the_money_goes_out(self):
        world = make_world()
        location, _, unit, invoice = await self._sale(world)
        document = await opened_return(world, invoice, location)

        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=PHONE_IMEI, customer_return_id=document.id
            )
        )
        result = await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=document.id)
        )

        assert result.data is not None
        assert result.data.status is DocumentStatus.CONFIRMED
        assert [m.quantity_delta for m in movements_of(world, unit.id)] == [1, -1, 1]
        assert booked(world, TransactionType.SALE_REVENUE, Currency.USD) == usd("520")
        assert booked(world, TransactionType.SALES_RETURN_REFUND, Currency.USD) == usd(
            "-520"
        )
        # The sale's -380 and the return's +380 cancel: the goods are back.
        assert booked(world, TransactionType.COGS, Currency.USD) == usd("0")

    async def test_the_handset_is_on_the_shelf_again(self):
        world = make_world()
        location, _, unit, invoice = await self._sale(world)
        document = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=PHONE_IMEI, customer_return_id=document.id
            )
        )

        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=document.id)
        )

        back = await world.units.get(unit.id)
        assert back is not None
        assert back.status is DeviceStatus.IN_STOCK
        assert back.location_id == location.id

    async def test_the_movement_says_it_was_a_return_not_a_reversed_sale(self):
        """§4.3: a sale that stood and was later unwound is two facts."""
        world = make_world()
        location, _, unit, invoice = await self._sale(world)
        document = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=PHONE_IMEI, customer_return_id=document.id
            )
        )

        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=document.id)
        )

        latest = movements_of(world, unit.id)[-1]
        assert latest.movement_type is MovementType.CUSTOMER_RETURN
        assert latest.document_type is DocumentType.CUSTOMER_RETURN


class TestOnlyWhatThisSaleSoldMayComeBack:
    """FR-4.9a: the invoice is what says which goods are returnable."""

    async def test_a_handset_from_another_invoice_is_refused_on_the_scan(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="520")
        await in_stock(world, product, location)
        other = catalogued(world, sku="SG24-128", price="700")
        await in_stock(world, other, location, imei=OTHER_IMEI)
        invoice = await sold(world, location, codes=(PHONE_IMEI,))
        document = await opened_return(world, invoice, location)

        with pytest.raises(UnitNotReturnableError):
            await world.scan_customer_return_line().handle(
                ScanCustomerReturnLineCommand(
                    code=OTHER_IMEI, customer_return_id=document.id
                )
            )

    async def test_a_draft_sale_cannot_be_returned_against(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="520")
        await in_stock(world, product, location)
        result = await world.create_sales_invoice().handle(
            CreateSalesInvoiceCommand(location_id=location.id, customer_id=None)
        )
        assert result.data is not None

        with pytest.raises(DocumentNotConfirmedError):
            await opened_return(world, result.data, location)

    async def test_the_same_handset_cannot_be_returned_twice(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="520")
        await in_stock(world, product, location)
        invoice = await sold(world, location)

        first = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(code=PHONE_IMEI, customer_return_id=first.id)
        )
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=first.id)
        )

        second = await opened_return(world, invoice, location)
        with pytest.raises(AlreadyReturnedError):
            await world.scan_customer_return_line().handle(
                ScanCustomerReturnLineCommand(
                    code=PHONE_IMEI, customer_return_id=second.id
                )
            )

    async def test_a_rescan_of_the_same_phone_is_a_no_op(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="520")
        await in_stock(world, product, location)
        invoice = await sold(world, location)
        document = await opened_return(world, invoice, location)

        for _ in range(3):
            result = await world.scan_customer_return_line().handle(
                ScanCustomerReturnLineCommand(
                    code=PHONE_IMEI, customer_return_id=document.id
                )
            )

        assert result.data is not None
        assert result.data.line_count == 1

    async def test_unscanning_removes_the_line(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="520")
        await in_stock(world, product, location)
        invoice = await sold(world, location)
        document = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=PHONE_IMEI, customer_return_id=document.id
            )
        )

        await world.unscan_customer_return_line().handle(
            UnscanCustomerReturnLineCommand(
                customer_return_id=document.id, imei=PHONE_IMEI
            )
        )

        held = await world.customer_returns.get(document.id)
        assert held is not None
        assert held.lines == []


class TestKeepingPartOfThePrice:
    """FR-4.9c: a restocking fee is a decision with a name on it."""

    async def _open_with_a_line(self, world: World):
        location = a_place(world)
        product = catalogued(world, price="520")
        await in_stock(world, product, location, cost="380")
        invoice = await sold(world, location)
        document = await opened_return(world, invoice, location)
        result = await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=PHONE_IMEI, customer_return_id=document.id
            )
        )
        assert result.data is not None
        return location, document, result.data.lines[0].id

    async def test_the_line_starts_at_what_the_sale_charged(self):
        world = make_world()
        _, document, _ = await self._open_with_a_line(world)

        held = await world.customer_returns.get(document.id)
        assert held is not None
        assert held.lines[0].refund_price == usd("520")
        assert not held.lines[0].is_reduced

    async def test_a_manager_may_keep_ten_percent(self):
        world = make_world()
        manager = uuid4()
        _, document, line_id = await self._open_with_a_line(world)

        await world.set_customer_return_refund(manager).handle(
            SetCustomerReturnRefundCommand(
                refund="468",
                note="opened box",
                customer_return_id=document.id,
                line_id=line_id,
            )
        )

        held = await world.customer_returns.get(document.id)
        assert held is not None
        assert held.lines[0].refund_price == usd("468")
        assert held.lines[0].refund_approved_by == manager

    async def test_the_kept_amount_never_reaches_the_ledger_as_revenue(self):
        """A restocking fee shrinks the refund; it does not book a sale."""
        world = make_world()
        _, document, line_id = await self._open_with_a_line(world)
        await world.set_customer_return_refund(uuid4()).handle(
            SetCustomerReturnRefundCommand(
                refund="468",
                note="opened box",
                customer_return_id=document.id,
                line_id=line_id,
            )
        )

        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=document.id)
        )

        assert booked(world, TransactionType.SALE_REVENUE, Currency.USD) == usd("520")
        assert booked(world, TransactionType.SALES_RETURN_REFUND, Currency.USD) == usd(
            "-468"
        )

    async def test_refunding_more_than_the_sale_took_is_refused(self):
        world = make_world()
        _, document, line_id = await self._open_with_a_line(world)

        with pytest.raises(RefundExceedsChargeError):
            await world.set_customer_return_refund(uuid4()).handle(
                SetCustomerReturnRefundCommand(
                    refund="600",
                    note="generous",
                    customer_return_id=document.id,
                    line_id=line_id,
                )
            )

    async def test_a_reduction_with_no_note_is_refused(self):
        world = make_world()
        _, document, line_id = await self._open_with_a_line(world)

        with pytest.raises(UnapprovedRefundError):
            await world.set_customer_return_refund(uuid4()).handle(
                SetCustomerReturnRefundCommand(
                    refund="468", customer_return_id=document.id, line_id=line_id
                )
            )


class TestAccessoriesComeBackAtWhatTheSaleBooked:
    """§4.6: the cost pool must not be diluted by a return."""

    async def test_a_partial_return_takes_its_share_of_the_original_cogs(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-BLK",
            price="50000",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            barcode=CASE_BARCODE,
        )
        # Three cases in at 90 000 so'm the lot: 30 000 each.
        await stocked_accessory(world, case, location, 3, uzs("90000"))
        invoice = await sold(world, location, codes=(CASE_BARCODE,) * 3)
        assert booked(world, TransactionType.COGS, Currency.UZS) == uzs("-90000")

        document = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=CASE_BARCODE, customer_return_id=document.id
            )
        )
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=document.id)
        )

        # One of three back: 30 000 of the 90 000 the sale booked.
        assert booked(world, TransactionType.COGS, Currency.UZS) == uzs("-60000")
        assert booked(world, TransactionType.SALES_RETURN_REFUND, Currency.UZS) == uzs(
            "-50000"
        )

    async def test_two_partial_returns_of_one_line_give_back_the_exact_cost(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-BLK",
            price="50000",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            barcode=CASE_BARCODE,
        )
        # Eight cases in at 100 so'm the lot: a cost that only divides
        # evenly across all eight at once, so two independently rounded
        # shares would sum to one so'm more than the sale booked.
        await stocked_accessory(world, case, location, 8, uzs("100"))
        invoice = await sold(world, location, codes=(CASE_BARCODE,) * 8)
        assert booked(world, TransactionType.COGS, Currency.UZS) == uzs("-100")

        first = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=CASE_BARCODE, customer_return_id=first.id
            )
        )
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=first.id)
        )

        second = await opened_return(world, invoice, location)
        for _ in range(7):
            await world.scan_customer_return_line().handle(
                ScanCustomerReturnLineCommand(
                    code=CASE_BARCODE, customer_return_id=second.id
                )
            )
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=second.id)
        )

        # All eight back: the positive COGS rows undo the sale's -100
        # exactly, with no rounded minor unit left behind.
        assert booked(world, TransactionType.COGS, Currency.UZS) == uzs("0")

    async def test_the_level_goes_back_up(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-BLK",
            price="50000",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 3, uzs("90000"))
        invoice = await sold(world, location, codes=(CASE_BARCODE,) * 3)
        document = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=CASE_BARCODE, customer_return_id=document.id
            )
        )

        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=document.id)
        )

        levels = [
            level
            for level in world.levels.by_id.values()
            if level.product_id == case.id and level.location_id == location.id
        ]
        assert [level.quantity for level in levels] == [1]

    async def test_returning_more_than_was_sold_is_refused(self):
        world = make_world()
        location = a_place(world)
        case = catalogued(
            world,
            sku="CASE-BLK",
            price="50000",
            tracking=TrackingType.QUANTITY,
            currency=Currency.UZS,
            barcode=CASE_BARCODE,
        )
        await stocked_accessory(world, case, location, 3, uzs("90000"))
        invoice = await sold(world, location, codes=(CASE_BARCODE,) * 2)
        document = await opened_return(world, invoice, location)
        for _ in range(2):
            await world.scan_customer_return_line().handle(
                ScanCustomerReturnLineCommand(
                    code=CASE_BARCODE, customer_return_id=document.id
                )
            )

        with pytest.raises(AlreadyReturnedError):
            await world.scan_customer_return_line().handle(
                ScanCustomerReturnLineCommand(
                    code=CASE_BARCODE, customer_return_id=document.id
                )
            )


class TestAReturnOnStoreCreditRelievesTheDebtFirst:
    """FR-4.9d: the customer stops owing before anybody hands over cash."""

    async def _credit_sale(self, world: World):
        location = a_place(world)
        product = catalogued(world, price="520")
        await in_stock(world, product, location, cost="380")
        customer = a_customer(world)
        invoice = await sold(
            world,
            location,
            customer=customer,
            payment_type=PaymentType.STORE_CREDIT,
            debt="7800000",
            down="800000",
        )
        return location, customer, invoice

    async def test_the_balance_drops_by_the_relief(self):
        world = make_world()
        location, _, invoice = await self._credit_sale(world)
        assert invoice.remaining_minor == 7_000_000

        document = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=PHONE_IMEI, customer_return_id=document.id
            )
        )
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(
                customer_return_id=document.id, debt_relief="7000000"
            )
        )

        after = await world.get_sales_invoice().handle(
            GetSalesInvoiceQuery(sales_invoice_id=invoice.id)
        )
        assert after.data is not None
        assert after.data.relieved_minor == 7_000_000
        assert after.data.remaining_minor == 0

    async def test_relief_above_the_balance_is_refused(self):
        world = make_world()
        location, _, invoice = await self._credit_sale(world)
        document = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=PHONE_IMEI, customer_return_id=document.id
            )
        )

        with pytest.raises(DebtReliefError):
            await world.confirm_customer_return().handle(
                ConfirmCustomerReturnCommand(
                    customer_return_id=document.id, debt_relief="7800000"
                )
            )

    async def test_relief_on_a_cash_sale_is_refused(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="520")
        await in_stock(world, product, location)
        invoice = await sold(world, location)
        document = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=PHONE_IMEI, customer_return_id=document.id
            )
        )

        with pytest.raises(DebtReliefError):
            await world.confirm_customer_return().handle(
                ConfirmCustomerReturnCommand(
                    customer_return_id=document.id, debt_relief="1000000"
                )
            )

    async def test_a_payment_cannot_settle_debt_a_return_already_relieved(self):
        world = make_world()
        location, _, invoice = await self._credit_sale(world)
        document = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=PHONE_IMEI, customer_return_id=document.id
            )
        )
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(
                customer_return_id=document.id, debt_relief="7000000"
            )
        )

        with pytest.raises(OverpaymentError):
            await world.record_payment().handle(
                RecordPaymentCommand(sales_invoice_id=invoice.id, amount="1000")
            )

    async def test_the_revenue_still_stands_at_its_full_amount(self):
        """§4.6: relief settles a debt; it never unwrites a sale."""
        world = make_world()
        location, _, invoice = await self._credit_sale(world)
        document = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=PHONE_IMEI, customer_return_id=document.id
            )
        )
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(
                customer_return_id=document.id, debt_relief="7000000"
            )
        )

        assert booked(world, TransactionType.SALE_REVENUE, Currency.USD) == usd("520")
        assert booked(world, TransactionType.PAYMENT_RECEIVED, Currency.UZS) == uzs(
            "800000"
        )


class TestCancellingAReturn:
    """FR-4.9g: the compensation sells the handset again."""

    async def _confirmed_return(self, world: World):
        location = a_place(world)
        product = catalogued(world, price="520")
        unit = await in_stock(world, product, location, cost="380")
        invoice = await sold(world, location)
        document = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=PHONE_IMEI, customer_return_id=document.id
            )
        )
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=document.id)
        )
        return location, unit, invoice, document

    async def test_the_original_rows_stay_and_their_negation_is_appended(self):
        world = make_world()
        _, unit, _, document = await self._confirmed_return(world)

        await world.cancel_customer_return().handle(
            CancelCustomerReturnCommand(
                customer_return_id=document.id, reason="wrong phone"
            )
        )

        assert [m.quantity_delta for m in movements_of(world, unit.id)] == [1, -1, 1, -1]
        assert booked(world, TransactionType.SALES_RETURN_REFUND, Currency.USD) == usd(
            "0"
        )
        assert booked(world, TransactionType.SALE_REVENUE, Currency.USD) == usd("520")

    async def test_the_handset_is_sold_again(self):
        world = make_world()
        _, unit, _, document = await self._confirmed_return(world)

        await world.cancel_customer_return().handle(
            CancelCustomerReturnCommand(customer_return_id=document.id, reason="mistake")
        )

        back = await world.units.get(unit.id)
        assert back is not None
        assert back.status is DeviceStatus.SOLD
        assert back.location_id is None

    async def test_a_cancelled_return_frees_the_handset_to_be_returned_again(self):
        world = make_world()
        location, _, invoice, document = await self._confirmed_return(world)
        await world.cancel_customer_return().handle(
            CancelCustomerReturnCommand(customer_return_id=document.id, reason="mistake")
        )

        second = await opened_return(world, invoice, location)
        result = await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=PHONE_IMEI, customer_return_id=second.id
            )
        )

        assert result.data is not None
        assert result.data.line_count == 1


class TestASaleWithAReturnCannotBeCancelled:
    """FR-4.9g: otherwise the goods come back twice."""

    async def test_cancelling_the_sale_is_refused(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="520")
        await in_stock(world, product, location)
        invoice = await sold(world, location)
        document = await opened_return(world, invoice, location)
        await world.scan_customer_return_line().handle(
            ScanCustomerReturnLineCommand(
                code=PHONE_IMEI, customer_return_id=document.id
            )
        )
        await world.confirm_customer_return().handle(
            ConfirmCustomerReturnCommand(customer_return_id=document.id)
        )

        with pytest.raises(InvoiceHasReturnsError):
            await world.cancel_sales_invoice().handle(
                CancelSalesInvoiceCommand(
                    sales_invoice_id=invoice.id, reason="changed our mind"
                )
            )

    async def test_a_draft_return_is_no_obstacle(self):
        world = make_world()
        location = a_place(world)
        product = catalogued(world, price="520")
        await in_stock(world, product, location)
        invoice = await sold(world, location)
        await opened_return(world, invoice, location)

        result = await world.cancel_sales_invoice().handle(
            CancelSalesInvoiceCommand(sales_invoice_id=invoice.id, reason="mistake")
        )

        assert result.data is not None
        assert result.data.status is DocumentStatus.CANCELLED
