"""Credit sales over HTTP, against real tables — PRD §4.7, §5.11, §8.

The application suite proves the rules against fakes. This one proves the
wiring: the migration, the grouped debt queries, the money ledger on real
rows, and the roles. The first class walks the M5b demo end to end — sell
a $600 phone on store credit for 7 800 000 so'm with an 800 000 down
payment, record two payments, then sell another through a credit company
and watch it settle with no debt at all.
"""

from tests.api.ledger_helpers import PHONE_IMEI, receive_phone, tenant_url  # noqa: F401
from tests.api.test_sales_api import open_invoice, price_unit

SECOND_IMEI = "356938035643809"


async def a_customer(client, owner, name="Aziz Karimov"):
    created = await client.post(
        "/api/v1/customers",
        headers=owner.auth,
        json={"fullName": name, "phone": "+998901234567"},
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]["id"]


async def a_company(client, owner, name="Uzum Nasiya"):
    created = await client.post(
        "/api/v1/credit-companies", headers=owner.auth, json={"name": name}
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]["id"]


async def a_scanned_invoice(
    client, settings, owner, *, customer_id=None, price="600", imei=PHONE_IMEI
):
    """One priced handset scanned onto a fresh invoice.

    Pass ``imei`` when a test needs a second sale: the IMEI is unique per
    store, so two handsets cannot share one.
    """
    unit_id, _, location_id = await receive_phone(client, settings, owner, imei=imei)
    await price_unit(client, owner, unit_id, price)
    body = {} if customer_id is None else {"customerId": customer_id}
    invoice = await open_invoice(client, owner, location_id, **body)
    scanned = await client.post(
        f"/api/v1/invoices/{invoice['id']}/scan",
        headers=owner.auth,
        json={"code": imei},
    )
    assert scanned.status_code == 200, scanned.text
    return invoice["id"]


async def confirm(client, owner, invoice_id, **terms):
    confirmed = await client.post(
        f"/api/v1/invoices/{invoice_id}/confirm", headers=owner.auth, json=terms
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()["data"]


async def a_seller(client, owner, email="seller@example.com"):
    invite = await client.post(
        "/api/v1/users/invite",
        headers=owner.auth,
        json={"email": email, "role": "tenant.seller"},
    )
    assert invite.status_code == 201, invite.text
    await client.post(
        "/api/v1/auth/accept-invite",
        json={"token": invite.json()["data"]["token"], "password": "sellerpass1"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "sellerpass1"}
    )
    return {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}


class TestTheStoreCreditDemo:
    """The M5b milestone demo, figure for figure."""

    async def test_confirming_opens_the_debt_and_banks_the_down_payment(
        self, client, settings, owner
    ):
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)

        sale = await confirm(
            client,
            owner,
            invoice_id,
            paymentType="store_credit",
            debt="7800000",
            downPayment="800000",
        )

        assert sale["paymentType"] == "store_credit"
        assert sale["debtMinor"] == 7_800_000
        assert sale["paidMinor"] == 800_000
        assert sale["remainingMinor"] == 7_000_000
        assert len(sale["payments"]) == 1

    async def test_revenue_is_still_booked_in_dollars(self, client, settings, owner):
        """FR-11.2: the phone leaves and the accrual happens whether or not
        money arrived — the som debt is the collection side."""
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)

        sale = await confirm(
            client, owner, invoice_id, paymentType="store_credit", debt="7800000"
        )

        assert sale["subtotals"] == [
            {"currency": "USD", "amount": "600.00", "amountMinor": 60000}
        ]

    async def test_two_payments_bring_the_balance_down(self, client, settings, owner):
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        await confirm(
            client,
            owner,
            invoice_id,
            paymentType="store_credit",
            debt="7800000",
            downPayment="800000",
        )

        for amount in ("2000000", "3000000"):
            paid = await client.post(
                f"/api/v1/invoices/{invoice_id}/payments",
                headers=owner.auth,
                json={"amount": amount, "method": "cash"},
            )
            assert paid.status_code == 201, paid.text

        assert paid.json()["data"]["remainingMinor"] == 2_000_000

    async def test_the_customer_account_shows_what_is_left_and_how_old(
        self, client, settings, owner
    ):
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        await confirm(
            client,
            owner,
            invoice_id,
            paymentType="store_credit",
            debt="7800000",
            downPayment="800000",
        )

        account = await client.get(
            f"/api/v1/customers/{customer_id}/account", headers=owner.auth
        )

        assert account.status_code == 200, account.text
        data = account.json()["data"]
        assert data["balanceMinor"] == 7_000_000
        assert data["openDebts"][0]["daysSinceSale"] == 0
        assert data["financedSales"] == []

    async def test_the_debtor_list_names_them(self, client, settings, owner):
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        await confirm(
            client,
            owner,
            invoice_id,
            paymentType="store_credit",
            debt="7800000",
            downPayment="800000",
        )

        listed = await client.get("/api/v1/reports/debtors", headers=owner.auth)

        assert listed.status_code == 200, listed.text
        rows = listed.json()["data"]
        assert [(r["fullName"], r["balanceMinor"]) for r in rows] == [
            ("Aziz Karimov", 7_000_000)
        ]

    async def test_the_balance_does_not_grow_with_the_number_of_payments(
        self, client, settings, owner
    ):
        """The debt is counted once, however many times it was paid against.

        Joining ``payments`` into the grouped query repeated the invoice
        once per payment row and summed its debt that many times, so three
        payments against a 7 200 000 debt reported 14 400 000 owed.
        """
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        await confirm(
            client,
            owner,
            invoice_id,
            paymentType="store_credit",
            debt="7200000",
            downPayment="200000",
        )
        for amount in ("1000000", "2000000"):
            await client.post(
                f"/api/v1/invoices/{invoice_id}/payments",
                headers=owner.auth,
                json={"amount": amount},
            )

        listed = await client.get("/api/v1/reports/debtors", headers=owner.auth)

        assert [r["balanceMinor"] for r in listed.json()["data"]] == [4_000_000]

    async def test_a_debt_paid_off_leaves_the_list(self, client, settings, owner):
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        await confirm(
            client,
            owner,
            invoice_id,
            paymentType="store_credit",
            debt="7200000",
            downPayment="200000",
        )
        for amount in ("1000000", "6000000"):
            await client.post(
                f"/api/v1/invoices/{invoice_id}/payments",
                headers=owner.auth,
                json={"amount": amount},
            )

        listed = await client.get("/api/v1/reports/debtors", headers=owner.auth)

        assert listed.json()["data"] == []

    async def test_a_settled_sale_does_not_age_a_customer_s_other_debt(
        self, client, settings, owner
    ):
        """The list is sorted and counted on open invoices only."""
        customer_id = await a_customer(client, owner)
        settled = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        await confirm(
            client, owner, settled, paymentType="store_credit", debt="500000",
            downPayment="500000",
        )
        still_owed = await a_scanned_invoice(
            client, settings, owner, customer_id=customer_id, imei=SECOND_IMEI
        )
        await confirm(
            client, owner, still_owed, paymentType="store_credit", debt="7200000"
        )

        listed = await client.get("/api/v1/reports/debtors", headers=owner.auth)

        rows = listed.json()["data"]
        assert [(r["balanceMinor"], r["openInvoiceCount"]) for r in rows] == [
            (7_200_000, 1)
        ]

    async def test_paying_more_than_is_owed_is_a_conflict(
        self, client, settings, owner
    ):
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        await confirm(
            client, owner, invoice_id, paymentType="store_credit", debt="7800000"
        )

        refused = await client.post(
            f"/api/v1/invoices/{invoice_id}/payments",
            headers=owner.auth,
            json={"amount": "7800001"},
        )

        assert refused.status_code == 409, refused.text


class TestTheCreditCompanyDemo:
    """FR-11.4: settled at confirm, with zero debt anywhere."""

    async def test_a_financed_sale_owes_nothing(self, client, settings, owner):
        company_id = await a_company(client, owner)
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)

        sale = await confirm(
            client,
            owner,
            invoice_id,
            paymentType="credit_company",
            creditCompanyId=company_id,
            contractRef="UZ-99417",
        )

        assert sale["debtMinor"] is None
        assert sale["remainingMinor"] == 0
        assert sale["payments"] == []

    async def test_the_customer_balance_stays_zero_and_the_sale_is_labelled(
        self, client, settings, owner
    ):
        """§4.7: attributing the company's debt to the customer would be the
        most misleading thing this system could do."""
        company_id = await a_company(client, owner)
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        await confirm(
            client,
            owner,
            invoice_id,
            paymentType="credit_company",
            creditCompanyId=company_id,
            contractRef="UZ-99417",
        )

        account = await client.get(
            f"/api/v1/customers/{customer_id}/account", headers=owner.auth
        )

        data = account.json()["data"]
        assert data["balanceMinor"] == 0
        assert data["openDebts"] == []
        assert data["financedSales"][0]["creditCompanyId"] == company_id
        assert data["financedSales"][0]["contractRef"] == "UZ-99417"

    async def test_no_debtor_appears_at_all(self, client, settings, owner):
        company_id = await a_company(client, owner)
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        await confirm(
            client,
            owner,
            invoice_id,
            paymentType="credit_company",
            creditCompanyId=company_id,
        )

        listed = await client.get("/api/v1/reports/debtors", headers=owner.auth)

        assert listed.json()["data"] == []

    async def test_the_sales_list_filters_by_payment_type(
        self, client, settings, owner
    ):
        company_id = await a_company(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(
            client,
            owner,
            invoice_id,
            paymentType="credit_company",
            creditCompanyId=company_id,
        )

        listed = await client.get("/api/v1/invoices", headers=owner.auth)

        rows = listed.json()["data"]
        assert [r["creditCompanyId"] for r in rows] == [company_id]


class TestLendingNeedsANamedCustomer:
    async def test_a_walk_in_cannot_take_store_credit(self, client, settings, owner):
        invoice_id = await a_scanned_invoice(client, settings, owner)

        refused = await client.post(
            f"/api/v1/invoices/{invoice_id}/confirm",
            headers=owner.auth,
            json={"paymentType": "store_credit", "debt": "7800000"},
        )

        assert refused.status_code == 422, refused.text
        assert "names no customer" in refused.json()["detail"]

    async def test_and_the_invoice_is_still_a_draft(self, client, settings, owner):
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await client.post(
            f"/api/v1/invoices/{invoice_id}/confirm",
            headers=owner.auth,
            json={"paymentType": "store_credit", "debt": "7800000"},
        )

        read = await client.get(f"/api/v1/invoices/{invoice_id}", headers=owner.auth)

        assert read.json()["data"]["status"] == "draft"


class TestReversingAPayment:
    """FR-11.8: compensation, never deletion."""

    async def test_the_original_stays_and_the_balance_goes_back_up(
        self, client, settings, owner
    ):
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        sale = await confirm(
            client,
            owner,
            invoice_id,
            paymentType="store_credit",
            debt="7800000",
            downPayment="800000",
        )
        payment_id = sale["payments"][0]["id"]

        reversed_sale = await client.post(
            f"/api/v1/payments/{payment_id}/reverse", headers=owner.auth
        )

        assert reversed_sale.status_code == 200, reversed_sale.text
        data = reversed_sale.json()["data"]
        assert data["remainingMinor"] == 7_800_000
        assert [p["amountMinor"] for p in data["payments"]] == [800_000, -800_000]

    async def test_reversing_twice_is_a_conflict(self, client, settings, owner):
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        sale = await confirm(
            client,
            owner,
            invoice_id,
            paymentType="store_credit",
            debt="7800000",
            downPayment="800000",
        )
        payment_id = sale["payments"][0]["id"]
        await client.post(f"/api/v1/payments/{payment_id}/reverse", headers=owner.auth)

        again = await client.post(
            f"/api/v1/payments/{payment_id}/reverse", headers=owner.auth
        )

        assert again.status_code == 409, again.text

    async def test_reversing_a_reversal_is_a_conflict(self, client, settings, owner):
        """FR-11.8: money comes back in as a fresh payment, not by undoing
        the undo."""
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        sale = await confirm(
            client,
            owner,
            invoice_id,
            paymentType="store_credit",
            debt="7800000",
            downPayment="800000",
        )
        payment_id = sale["payments"][0]["id"]
        undone = await client.post(
            f"/api/v1/payments/{payment_id}/reverse", headers=owner.auth
        )
        compensating = next(
            p for p in undone.json()["data"]["payments"] if p["isReversal"]
        )

        again = await client.post(
            f"/api/v1/payments/{compensating['id']}/reverse", headers=owner.auth
        )

        assert again.status_code == 409, again.text


class TestCancellingAStoreCreditSale:
    """FR-11.11: the debt is void, the payments are not."""

    async def test_the_debt_goes_and_the_payments_stay(self, client, settings, owner):
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        await confirm(
            client,
            owner,
            invoice_id,
            paymentType="store_credit",
            debt="7800000",
            downPayment="800000",
        )

        cancelled = await client.post(
            f"/api/v1/invoices/{invoice_id}/cancel",
            headers=owner.auth,
            json={"reason": "wrong handset"},
        )

        assert cancelled.status_code == 200, cancelled.text
        data = cancelled.json()["data"]
        assert data["remainingMinor"] == 0
        assert data["paidMinor"] == 800_000

    async def test_the_customer_owes_nothing_afterwards(self, client, settings, owner):
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        await confirm(
            client, owner, invoice_id, paymentType="store_credit", debt="7800000"
        )
        await client.post(
            f"/api/v1/invoices/{invoice_id}/cancel", headers=owner.auth, json={}
        )

        listed = await client.get("/api/v1/reports/debtors", headers=owner.auth)

        assert listed.json()["data"] == []


class TestWhoMaySellOnCredit:
    """§2.1's matrix, over the six new routes."""

    async def test_a_seller_may_lend_and_collect_but_not_reverse(
        self, client, settings, owner, create_tenant
    ):
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
        seller = await a_seller(client, owner)

        sale = await client.post(
            f"/api/v1/invoices/{invoice_id}/confirm",
            headers=seller,
            json={
                "paymentType": "store_credit",
                "debt": "7800000",
                "downPayment": "800000",
            },
        )
        assert sale.status_code == 200, sale.text

        collected = await client.post(
            f"/api/v1/invoices/{invoice_id}/payments",
            headers=seller,
            json={"amount": "1000000"},
        )
        assert collected.status_code == 201, collected.text

        payment_id = sale.json()["data"]["payments"][0]["id"]
        refused = await client.post(
            f"/api/v1/payments/{payment_id}/reverse", headers=seller
        )
        assert refused.status_code == 403, refused.text

    async def test_a_seller_reads_the_companies_but_does_not_maintain_them(
        self, client, settings, owner, create_tenant
    ):
        await a_company(client, owner)
        seller = await a_seller(client, owner, "seller2@example.com")

        readable = await client.get("/api/v1/credit-companies", headers=seller)
        assert readable.status_code == 200, readable.text

        refused = await client.post(
            "/api/v1/credit-companies", headers=seller, json={"name": "Alif Nasiya"}
        )
        assert refused.status_code == 403, refused.text

    async def test_a_seller_reads_one_account_but_not_the_whole_book(
        self, client, settings, owner, create_tenant
    ):
        """§2.1 note 1: serving the customer in front of you is a different
        question from the store's total exposure."""
        customer_id = await a_customer(client, owner)
        seller = await a_seller(client, owner, "seller3@example.com")

        account = await client.get(
            f"/api/v1/customers/{customer_id}/account", headers=seller
        )
        assert account.status_code == 200, account.text

        refused = await client.get("/api/v1/reports/debtors", headers=seller)
        assert refused.status_code == 403, refused.text
