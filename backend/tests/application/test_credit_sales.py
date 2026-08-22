"""Credit sales and customer debt through the handlers — PRD §4.7, §5.11.

No database. What these cover that the domain tests cannot is everything
needing a lookup: what a balance actually comes to once payments are
counted, what the money ledger holds afterwards, and the refusals that
only a query can reach.

The class that matters most is ``TestCancellingVoidsTheDebtAndKeepsThePayments``.
FR-11.11 is the one place where "compensate, never delete" and "the debt
is void" have to hold at the same time, and getting it wrong means either
a customer who still owes money for a phone they gave back, or a refund
the store has no record of owing.
"""

from uuid import uuid4

import pytest

from application.commands.cancel_sales_invoice import CancelSalesInvoiceCommand
from application.commands.confirm_sales_invoice import ConfirmSalesInvoiceCommand
from application.commands.create_credit_company import CreateCreditCompanyCommand
from application.commands.create_sales_invoice import CreateSalesInvoiceCommand
from application.commands.record_payment import RecordPaymentCommand
from application.commands.reverse_payment import ReversePaymentCommand
from application.commands.scan_invoice_line import ScanInvoiceLineCommand
from application.dtos import MoneyEffect, Posting, PostingEntry
from application.queries.get_customer_account import GetCustomerAccountQuery
from application.queries.list_debtors import ListDebtorsQuery
from domain.entities import Customer, DeviceUnit, Location, Product
from domain.enums import (
    DeviceCondition,
    DeviceStatus,
    DocumentType,
    MovementType,
    PaymentMethod,
    PaymentType,
    TrackingType,
    TransactionType,
)
from domain.errors import (
    AnonymousDebtError,
    CreditTermsError,
    NotACreditSaleError,
    OverpaymentError,
    PaymentAlreadyReversedError,
)
from domain.value_objects import IMEI, SKU, Currency, Money
from tests.application.builders import World, make_world

PHONE_IMEI = "490154203237518"


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


def som(major: str) -> Money:
    return Money.from_major(major, Currency.UZS)


def a_place(world: World) -> Location:
    location = Location(name="Shop", is_active=True, created_at=world.clock.now())
    world.locations.by_id[location.id] = location
    return location


def a_customer(world: World, name: str = "Aziz") -> Customer:
    customer = Customer(full_name=name, is_active=True, created_at=world.clock.now())
    world.customers.by_id[customer.id] = customer
    return customer


def catalogued(world: World, price: str = "600") -> Product:
    product = Product(
        sku=SKU.parse("IP15P-256"),
        name="iPhone 15 Pro",
        tracking_type=TrackingType.SERIAL,
        currency=Currency.USD,
        default_sale_price=usd(price),
        is_active=True,
        created_at=world.clock.now(),
    )
    world.products.by_id[product.id] = product
    return product


async def in_stock(
    world: World, product: Product, location: Location, imei: str = PHONE_IMEI
) -> DeviceUnit:
    unit = DeviceUnit(
        imei=IMEI.parse(imei),
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
    return unit


async def a_scanned_invoice(
    world: World, location: Location, customer: Customer | None = None, imei: str = PHONE_IMEI
):
    result = await world.create_sales_invoice().handle(
        CreateSalesInvoiceCommand(
            location_id=location.id,
            customer_id=None if customer is None else customer.id,
        )
    )
    assert result.data is not None
    invoice = await world.invoices.get(result.data.id)
    assert invoice is not None
    await world.scan_invoice_line().handle(
        ScanInvoiceLineCommand(code=imei, sales_invoice_id=invoice.id)
    )
    return await world.invoices.get(invoice.id)


async def sold_on_credit(
    world: World,
    *,
    debt: str = "7800000",
    down: str | None = "800000",
    price: str = "600",
    customer: Customer | None = None,
    location: Location | None = None,
):
    """The milestone demo's opening move, as a fixture.

    A $600 phone leaves on store credit for 7 800 000 so'm with an
    800 000 down payment (FR-11.5).
    """
    location = location or a_place(world)
    customer = customer or a_customer(world)
    product = catalogued(world, price)
    await in_stock(world, product, location)
    invoice = await a_scanned_invoice(world, location, customer)
    assert invoice is not None

    result = await world.confirm_sales_invoice().handle(
        ConfirmSalesInvoiceCommand(
            sales_invoice_id=invoice.id,
            payment_type=PaymentType.STORE_CREDIT,
            debt=debt,
            down_payment=down,
        )
    )
    assert result.data is not None
    return result.data


def booked(world: World, txn_type: TransactionType) -> Money:
    total = None
    for txn in world.transactions.rows:
        if txn.txn_type is not txn_type:
            continue
        total = txn.amount if total is None else total + txn.amount
    return total or Money.zero(Currency.UZS)


class TestSellingOnStoreCredit:
    """FR-11.5's worked example, figure for figure."""

    async def test_the_phone_leaves_and_revenue_is_booked_in_full(self):
        """FR-11.2: goods and accrual do not care whether money arrived."""
        world = make_world()

        await sold_on_credit(world)

        assert booked(world, TransactionType.SALE_REVENUE) == usd("600")
        assert booked(world, TransactionType.COGS) == usd("-380")

    async def test_the_down_payment_is_recorded_as_the_first_payment(self):
        """FR-11.5: not netted off the debt, so ``remaining = debt − Σ
        payments`` holds with no special case."""
        world = make_world()

        await sold_on_credit(world)

        assert [p.amount for p in world.payments.rows] == [som("800000")]

    async def test_the_customer_owes_exactly_seven_million(self):
        world = make_world()

        invoice = await sold_on_credit(world)

        assert invoice.debt_minor == 7_800_000
        assert invoice.paid_minor == 800_000
        assert invoice.remaining_minor == 7_000_000

    async def test_the_down_payment_is_cash_collected_like_any_other(self):
        world = make_world()

        await sold_on_credit(world)

        assert booked(world, TransactionType.PAYMENT_RECEIVED) == som("800000")

    async def test_a_sale_with_no_down_payment_owes_the_whole_debt(self):
        world = make_world()

        invoice = await sold_on_credit(world, down=None)

        assert invoice.remaining_minor == 7_800_000
        assert world.payments.rows == []

    async def test_lending_to_a_walk_in_is_refused(self):
        world = make_world()
        location = a_place(world)
        await in_stock(world, catalogued(world), location)
        invoice = await a_scanned_invoice(world, location)
        assert invoice is not None

        with pytest.raises(AnonymousDebtError):
            await world.confirm_sales_invoice().handle(
                ConfirmSalesInvoiceCommand(
                    sales_invoice_id=invoice.id,
                    payment_type=PaymentType.STORE_CREDIT,
                    debt="7800000",
                )
            )


class TestAFinancedSaleIsSettledAtConfirm:
    """FR-11.4: the company pays the store in full, so nothing is owed."""

    async def _financed(self, world: World, *, active: bool = True):
        created = await world.create_credit_company().handle(
            CreateCreditCompanyCommand(name="Uzum Nasiya")
        )
        assert created.data is not None
        if not active:
            company = await world.credit_companies.get(created.data.id)
            assert company is not None
            company.is_active = False

        location = a_place(world)
        customer = a_customer(world)
        await in_stock(world, catalogued(world), location)
        invoice = await a_scanned_invoice(world, location, customer)
        assert invoice is not None
        return customer, invoice, created.data.id

    async def test_it_creates_no_debt_and_no_payment(self):
        world = make_world()
        _, invoice, company_id = await self._financed(world)

        result = await world.confirm_sales_invoice().handle(
            ConfirmSalesInvoiceCommand(
                sales_invoice_id=invoice.id,
                payment_type=PaymentType.CREDIT_COMPANY,
                credit_company_id=company_id,
                contract_ref="UZ-99417",
            )
        )

        assert result.data is not None
        assert result.data.debt_minor is None
        assert result.data.remaining_minor == 0
        assert world.payments.rows == []

    async def test_the_customer_balance_stays_at_zero(self):
        world = make_world()
        customer, invoice, company_id = await self._financed(world)
        await world.confirm_sales_invoice().handle(
            ConfirmSalesInvoiceCommand(
                sales_invoice_id=invoice.id,
                payment_type=PaymentType.CREDIT_COMPANY,
                credit_company_id=company_id,
            )
        )

        account = await world.get_customer_account().handle(
            GetCustomerAccountQuery(customer_id=customer.id)
        )

        assert account.data is not None
        assert account.data.balance_minor == 0
        assert len(account.data.financed_sales) == 1
        assert account.data.open_debts == []

    async def test_the_sale_is_labelled_with_the_company_that_financed_it(self):
        world = make_world()
        customer, invoice, company_id = await self._financed(world)
        await world.confirm_sales_invoice().handle(
            ConfirmSalesInvoiceCommand(
                sales_invoice_id=invoice.id,
                payment_type=PaymentType.CREDIT_COMPANY,
                credit_company_id=company_id,
                contract_ref="UZ-99417",
            )
        )

        account = await world.get_customer_account().handle(
            GetCustomerAccountQuery(customer_id=customer.id)
        )

        assert account.data is not None
        financed = account.data.financed_sales[0]
        assert financed.credit_company_id == company_id
        assert financed.contract_ref == "UZ-99417"
        assert financed.remaining_minor == 0

    async def test_a_retired_partner_cannot_finance_a_new_sale(self):
        world = make_world()
        _, invoice, company_id = await self._financed(world, active=False)

        with pytest.raises(CreditTermsError):
            await world.confirm_sales_invoice().handle(
                ConfirmSalesInvoiceCommand(
                    sales_invoice_id=invoice.id,
                    payment_type=PaymentType.CREDIT_COMPANY,
                    credit_company_id=company_id,
                )
            )

    async def test_no_payment_may_be_recorded_against_it(self):
        world = make_world()
        _, invoice, company_id = await self._financed(world)
        await world.confirm_sales_invoice().handle(
            ConfirmSalesInvoiceCommand(
                sales_invoice_id=invoice.id,
                payment_type=PaymentType.CREDIT_COMPANY,
                credit_company_id=company_id,
            )
        )

        with pytest.raises(NotACreditSaleError):
            await world.record_payment().handle(
                RecordPaymentCommand(sales_invoice_id=invoice.id, amount="100000")
            )


class TestPayingDownADebt:
    async def test_each_payment_takes_money_off_what_is_left(self):
        world = make_world()
        sale = await sold_on_credit(world)

        await world.record_payment().handle(
            RecordPaymentCommand(sales_invoice_id=sale.id, amount="2000000")
        )
        result = await world.record_payment().handle(
            RecordPaymentCommand(sales_invoice_id=sale.id, amount="3000000")
        )

        assert result.data is not None
        assert result.data.remaining_minor == 2_000_000

    async def test_a_payment_records_how_the_money_arrived(self):
        world = make_world()
        sale = await sold_on_credit(world)

        result = await world.record_payment().handle(
            RecordPaymentCommand(
                sales_invoice_id=sale.id,
                amount="1000000",
                method=PaymentMethod.TRANSFER,
                note="bank transfer, ref 88121",
            )
        )

        assert result.data is not None
        latest = result.data.payments[-1]
        assert latest.method is PaymentMethod.TRANSFER
        assert latest.note == "bank transfer, ref 88121"

    async def test_paying_more_than_is_owed_is_refused(self):
        """FR-11.6: the balance is a projection of append-only rows, so it
        can only stay non-negative if the rows are refused up front."""
        world = make_world()
        sale = await sold_on_credit(world)

        with pytest.raises(OverpaymentError):
            await world.record_payment().handle(
                RecordPaymentCommand(sales_invoice_id=sale.id, amount="7000001")
            )

    async def test_the_refused_payment_writes_nothing(self):
        world = make_world()
        sale = await sold_on_credit(world)

        with pytest.raises(OverpaymentError):
            await world.record_payment().handle(
                RecordPaymentCommand(sales_invoice_id=sale.id, amount="9000000")
            )

        assert len(world.payments.rows) == 1

    async def test_paying_the_debt_off_exactly_is_allowed(self):
        world = make_world()
        sale = await sold_on_credit(world)

        result = await world.record_payment().handle(
            RecordPaymentCommand(sales_invoice_id=sale.id, amount="7000000")
        )

        assert result.data is not None
        assert result.data.remaining_minor == 0


class TestAPaymentIsNeverRevenue:
    """FR-11.7 and §11's "double-counting revenue as cash" risk row — the
    signature bug of naive credit systems."""

    async def test_paying_a_sale_down_to_zero_books_its_price_exactly_once(self):
        world = make_world()
        sale = await sold_on_credit(world)

        for amount in ("2000000", "2000000", "3000000"):
            await world.record_payment().handle(
                RecordPaymentCommand(sales_invoice_id=sale.id, amount=amount)
            )

        assert booked(world, TransactionType.SALE_REVENUE) == usd("600")

    async def test_the_cash_collected_is_a_separate_category_in_som(self):
        world = make_world()
        sale = await sold_on_credit(world)
        await world.record_payment().handle(
            RecordPaymentCommand(sales_invoice_id=sale.id, amount="2000000")
        )

        assert booked(world, TransactionType.PAYMENT_RECEIVED) == som("2800000")

    async def test_a_payment_names_itself_in_the_ledger_not_the_invoice(self):
        """The reason cancelling a sale can leave its payments standing."""
        world = make_world()
        await sold_on_credit(world)

        payment = world.payments.rows[0]
        rows = [
            txn
            for txn in world.transactions.rows
            if txn.txn_type is TransactionType.PAYMENT_RECEIVED
        ]
        assert [(r.document_type, r.document_id) for r in rows] == [
            (DocumentType.PAYMENT, payment.id)
        ]


class TestReversingAPayment:
    """FR-11.8: compensation, never deletion."""

    async def test_the_original_stays_and_a_negative_row_joins_it(self):
        world = make_world()
        await sold_on_credit(world)
        original = world.payments.rows[0]

        await world.reverse_payment().handle(ReversePaymentCommand(payment_id=original.id))

        assert [p.amount for p in world.payments.rows] == [som("800000"), som("-800000")]

    async def test_the_balance_goes_back_up_by_what_came_off_it(self):
        world = make_world()
        await sold_on_credit(world)
        original = world.payments.rows[0]

        result = await world.reverse_payment().handle(
            ReversePaymentCommand(payment_id=original.id)
        )

        assert result.data is not None
        assert result.data.remaining_minor == 7_800_000

    async def test_the_money_ledger_nets_to_zero_for_that_payment(self):
        world = make_world()
        await sold_on_credit(world)
        original = world.payments.rows[0]

        await world.reverse_payment().handle(ReversePaymentCommand(payment_id=original.id))

        assert booked(world, TransactionType.PAYMENT_RECEIVED) == som("0")

    async def test_reversing_twice_is_refused(self):
        """It would re-apply the payment, and the compensating row is the
        only guard — the ledger holds none of its own."""
        world = make_world()
        await sold_on_credit(world)
        original = world.payments.rows[0]
        await world.reverse_payment().handle(ReversePaymentCommand(payment_id=original.id))

        with pytest.raises(PaymentAlreadyReversedError):
            await world.reverse_payment().handle(
                ReversePaymentCommand(payment_id=original.id)
            )


class TestCancellingVoidsTheDebtAndKeepsThePayments:
    """FR-11.11, the one place both rules have to hold at once."""

    async def _cancelled(self, world: World):
        sale = await sold_on_credit(world)
        result = await world.cancel_sales_invoice().handle(
            CancelSalesInvoiceCommand(sales_invoice_id=sale.id, reason="wrong handset")
        )
        assert result.data is not None
        return result.data

    async def test_stock_and_money_reverse_as_they_do_for_a_cash_sale(self):
        world = make_world()

        await self._cancelled(world)

        assert booked(world, TransactionType.SALE_REVENUE) == usd("0")
        assert booked(world, TransactionType.COGS) == usd("0")

    async def test_the_debt_is_void(self):
        world = make_world()

        cancelled = await self._cancelled(world)

        assert cancelled.remaining_minor == 0

    async def test_the_payments_are_surfaced_and_never_silently_deleted(self):
        world = make_world()

        cancelled = await self._cancelled(world)

        assert cancelled.paid_minor == 800_000
        assert len(cancelled.payments) == 1
        assert booked(world, TransactionType.PAYMENT_RECEIVED) == som("800000")

    async def test_the_customer_owes_nothing_afterwards(self):
        world = make_world()
        customer = a_customer(world)
        location = a_place(world)
        sale = await sold_on_credit(world, customer=customer, location=location)
        await world.cancel_sales_invoice().handle(
            CancelSalesInvoiceCommand(sales_invoice_id=sale.id)
        )

        account = await world.get_customer_account().handle(
            GetCustomerAccountQuery(customer_id=customer.id)
        )

        assert account.data is not None
        assert account.data.balance_minor == 0

    async def test_no_new_payment_may_be_recorded_against_it(self):
        world = make_world()
        cancelled = await self._cancelled(world)

        with pytest.raises(NotACreditSaleError):
            await world.record_payment().handle(
                RecordPaymentCommand(sales_invoice_id=cancelled.id, amount="100000")
            )

    async def test_a_payment_taken_in_error_can_still_be_refunded(self):
        """Reversing is how the refund is recorded, so it stays open on a
        cancelled invoice."""
        world = make_world()
        await self._cancelled(world)
        original = world.payments.rows[0]

        result = await world.reverse_payment().handle(
            ReversePaymentCommand(payment_id=original.id)
        )

        assert result.data is not None
        assert result.data.paid_minor == 0


class TestTheCustomerAccount:
    """FR-11.9."""

    async def test_the_balance_is_the_sum_of_what_is_left_on_each_invoice(self):
        world = make_world()
        customer = a_customer(world)
        location = a_place(world)
        await sold_on_credit(world, customer=customer, location=location)

        account = await world.get_customer_account().handle(
            GetCustomerAccountQuery(customer_id=customer.id)
        )

        assert account.data is not None
        assert account.data.balance_minor == 7_000_000

    async def test_an_open_debt_reports_its_age(self):
        world = make_world()
        customer = a_customer(world)
        location = a_place(world)
        await sold_on_credit(world, customer=customer, location=location)
        world.clock.current = world.clock.current.replace(month=9)

        account = await world.get_customer_account().handle(
            GetCustomerAccountQuery(customer_id=customer.id)
        )

        assert account.data is not None
        assert account.data.open_debts[0].days_since_sale == 62

    async def test_a_cash_customer_has_no_account_entries_at_all(self):
        world = make_world()
        customer = a_customer(world)
        location = a_place(world)
        await in_stock(world, catalogued(world), location)
        invoice = await a_scanned_invoice(world, location, customer)
        assert invoice is not None
        await world.confirm_sales_invoice().handle(
            ConfirmSalesInvoiceCommand(sales_invoice_id=invoice.id)
        )

        account = await world.get_customer_account().handle(
            GetCustomerAccountQuery(customer_id=customer.id)
        )

        assert account.data is not None
        assert account.data.balance_minor == 0
        assert account.data.open_debts == []
        assert account.data.financed_sales == []


class TestTheDebtorList:
    """FR-11.10: who owes what, oldest debt first."""

    async def test_a_settled_customer_drops_off_the_list(self):
        world = make_world()
        customer = a_customer(world)
        location = a_place(world)
        sale = await sold_on_credit(world, customer=customer, location=location)
        await world.record_payment().handle(
            RecordPaymentCommand(sales_invoice_id=sale.id, amount="7000000")
        )

        listed = await world.list_debtors().handle(ListDebtorsQuery())

        assert listed.data == []

    async def test_a_debtor_is_reported_with_their_som_balance(self):
        world = make_world()
        customer = a_customer(world)
        location = a_place(world)
        await sold_on_credit(world, customer=customer, location=location)

        listed = await world.list_debtors().handle(ListDebtorsQuery())

        assert listed.data is not None
        assert [d.balance_minor for d in listed.data] == [7_000_000]

    async def test_the_oldest_debt_comes_first(self):
        """Store credit has no due date (§4.7), so age is what makes a
        stale debt visible."""
        world = make_world()
        location = a_place(world)
        old_debtor, new_debtor = a_customer(world, "Aziz"), a_customer(world, "Bek")

        await sold_on_credit(world, customer=old_debtor, location=location)
        world.clock.current = world.clock.current.replace(month=9)
        product = catalogued(world, "600")
        await in_stock(world, product, location, imei="356938035643809")
        invoice = await a_scanned_invoice(
            world, location, new_debtor, imei="356938035643809"
        )
        assert invoice is not None
        await world.confirm_sales_invoice().handle(
            ConfirmSalesInvoiceCommand(
                sales_invoice_id=invoice.id,
                payment_type=PaymentType.STORE_CREDIT,
                debt="9000000",
            )
        )

        listed = await world.list_debtors().handle(ListDebtorsQuery())

        assert listed.data is not None
        assert [d.customer_id for d in listed.data] == [old_debtor.id, new_debtor.id]

    async def test_a_financed_customer_never_appears(self):
        """§4.7: attributing a company's debt to the customer would be the
        most misleading thing this system could do."""
        world = make_world()
        created = await world.create_credit_company().handle(
            CreateCreditCompanyCommand(name="Alif Nasiya")
        )
        assert created.data is not None
        location = a_place(world)
        customer = a_customer(world)
        await in_stock(world, catalogued(world), location)
        invoice = await a_scanned_invoice(world, location, customer)
        assert invoice is not None
        await world.confirm_sales_invoice().handle(
            ConfirmSalesInvoiceCommand(
                sales_invoice_id=invoice.id,
                payment_type=PaymentType.CREDIT_COMPANY,
                credit_company_id=created.data.id,
            )
        )

        listed = await world.list_debtors().handle(ListDebtorsQuery())

        assert listed.data == []


class TestBalancesReconcile:
    """§4.7, FR-10.7b: ``verify-balances`` reports and never repairs."""

    async def test_a_healthy_store_reconciles(self):
        world = make_world()
        sale = await sold_on_credit(world)
        await world.record_payment().handle(
            RecordPaymentCommand(sales_invoice_id=sale.id, amount="2000000")
        )

        assert await world.balance_verifier().verify() == []

    async def test_a_payment_the_ledger_never_saw_is_reported(self):
        world = make_world()
        sale = await sold_on_credit(world)
        rogue = world.payments.rows[0]
        world.payments.rows.append(
            rogue.__class__(
                sales_invoice_id=sale.id,
                occurred_at=world.clock.now(),
                amount=som("500000"),
                method=PaymentMethod.CASH,
                user_id=rogue.user_id,
            )
        )

        findings = await world.balance_verifier().verify()

        assert len(findings) == 1
        assert "cash collected" in findings[0].subject

    async def test_a_debt_smaller_than_what_was_collected_is_reported(self):
        world = make_world()
        sale = await sold_on_credit(world)
        invoice = await world.invoices.get(sale.id)
        assert invoice is not None
        invoice.debt = som("500000")

        findings = await world.balance_verifier().verify()

        assert [f.subject for f in findings] == [f"debt on {invoice.number}"]
