"""What the customer actually handed over on a sale settled at the counter.

The gap this closes: a $600 handset paid for in cash som booked revenue in
dollars and recorded no som figure anywhere, so a till could not be balanced
at the end of a shift. The tender is the som figure, sitting beside the
dollar revenue and never netted against it — there is still no rate in the
system, and the two numbers are two independent facts about one sale.

All of it is behind ``runsTill``, off until a store says it balances a
drawer. The last class here is the off state, which has to be exactly the
system V1 shipped.
"""

from infrastructure.cli import _verify
from tests.api.ledger_helpers import (  # noqa: F401
    PHONE_IMEI,
    receive_phone,
    tenant_url,
)
from tests.api.test_credit_api import (
    SECOND_IMEI,
    a_company,
    a_customer,
    a_scanned_invoice,
    confirm,
)

API = "/api/v1"


TRADE_IN_IMEI = "351756051523993"


async def a_trade_in(client, settings, owner, *, cost="330.00", cash="4200000"):
    """The §4.5b walk-in: booked in the product's currency, paid in som."""
    _, product_id, location_id = await receive_phone(
        client, settings, owner, imei=PHONE_IMEI
    )
    opened = await client.post(
        f"{API}/receipts",
        headers=owner.auth,
        json={
            "locationId": str(location_id),
            "acquisitionSource": "trade_in",
            "lines": [{"productId": str(product_id), "quantity": 1}],
        },
    )
    assert opened.status_code == 201, opened.text
    receipt_id = opened.json()["data"]["id"]
    scanned = await client.post(
        f"{API}/receipts/{receipt_id}/scan",
        headers=owner.auth,
        json={
            "imei": TRADE_IN_IMEI,
            "condition": "used",
            "acquisitionCost": cost,
            "askingPrice": "420.00",
            "cashPaid": cash,
            "cashPaidCurrency": "UZS",
        },
    )
    assert scanned.status_code == 200, scanned.text
    confirmed = await client.post(
        f"{API}/receipts/{receipt_id}/confirm", headers=owner.auth, json={}
    )
    assert confirmed.status_code == 200, confirmed.text
    return receipt_id


async def keep_a_till(client, owner, runs_till=True):
    """Turn the drawer on. Off is the default, so every till test says so."""
    updated = await client.put(
        f"{API}/settings/tenant",
        headers=owner.auth,
        json={"timezone": "Asia/Tashkent", "runsTill": runs_till},
    )
    assert updated.status_code == 200, updated.text
    return updated.json()["data"]


async def tender(client, owner, invoice_id, amount, currency="UZS", **rest):
    return await client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        headers=owner.auth,
        json={"amount": amount, "currency": currency, **rest},
    )


async def ledger_by_type(client, owner):
    rows = await client.get("/api/v1/reports/financial-ledger", headers=owner.auth)
    assert rows.status_code == 200, rows.text
    return rows.json()["data"]


class TestASomTenderAgainstADollarSale:
    """The case §4 left open: priced in USD, paid in som."""

    async def test_the_som_figure_is_recorded_and_the_revenue_stays_in_dollars(
        self, client, settings, owner
    ):
        await keep_a_till(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner)
        sale = await confirm(client, owner, invoice_id)

        assert sale["subtotals"] == [{"currency": "USD", "minor": 60000}]

        taken = await tender(client, owner, invoice_id, "7620000")
        assert taken.status_code == 201, taken.text
        data = taken.json()["data"]

        assert data["tendered"] == [{"currency": "UZS", "minor": 7_620_000}]
        # The sale is still booked at $600. Nothing converted either figure
        # into the other, and no field holds their sum.
        assert data["subtotals"] == [{"currency": "USD", "minor": 60000}]

    async def test_it_books_a_tender_and_never_revenue(self, client, settings, owner):
        await keep_a_till(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(client, owner, invoice_id)
        await tender(client, owner, invoice_id, "7620000")

        booked = {
            (row["txnType"], row["amount"]["currency"]): row["amount"]["minor"]
            for row in await ledger_by_type(client, owner)
        }

        assert booked[("tender_received", "UZS")] == 7_620_000
        assert booked[("sale_revenue", "USD")] == 60000
        # FR-11.7: a payment never writes revenue, in either currency.
        assert ("sale_revenue", "UZS") not in booked

    async def test_a_dollar_tender_is_recorded_in_dollars(
        self, client, settings, owner
    ):
        await keep_a_till(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(client, owner, invoice_id)

        taken = await tender(client, owner, invoice_id, "600.00", currency="USD")

        assert taken.status_code == 201, taken.text
        assert taken.json()["data"]["tendered"] == [
            {"currency": "USD", "minor": 60000}
        ]

    async def test_two_currencies_across_a_sale_stay_apart(
        self, client, settings, owner
    ):
        """Half in dollars and half in som is two totals, never one."""
        await keep_a_till(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(client, owner, invoice_id)

        await tender(client, owner, invoice_id, "300.00", currency="USD")
        taken = await tender(client, owner, invoice_id, "3810000")

        assert taken.json()["data"]["tendered"] == [
            {"currency": "USD", "minor": 30000},
            {"currency": "UZS", "minor": 3_810_000},
        ]


class TestTenderingAtConfirm:
    async def test_the_confirm_records_what_was_taken(self, client, settings, owner):
        await keep_a_till(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner)

        sale = await confirm(client, owner, invoice_id, tendered="7620000")

        assert sale["tendered"] == [{"currency": "UZS", "minor": 7_620_000}]

    async def test_a_confirm_that_states_nothing_records_nothing(
        self, client, settings, owner
    ):
        """A store that does not run a till is unaffected (FR-11.1)."""
        await keep_a_till(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner)

        sale = await confirm(client, owner, invoice_id)

        assert sale["tendered"] == []
        assert sale["payments"] == []


class TestWhatATenderIsNot:
    async def test_it_settles_no_debt_and_leaves_the_balance_alone(
        self, client, settings, owner
    ):
        """A som tender is not a debt payment: a paid-in-full sale owes
        nothing before it and nothing after."""
        await keep_a_till(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(client, owner, invoice_id)

        taken = await tender(client, owner, invoice_id, "7620000")

        data = taken.json()["data"]
        assert data["debt"] is None
        assert data["remaining"]["minor"] == 0

    async def test_a_credit_company_sale_takes_none(self, client, settings, owner):
        """The company settles with the store, so nothing crosses the counter."""
        await keep_a_till(client, owner)
        customer_id = await a_customer(client, owner)
        company_id = await a_company(client, owner)
        invoice_id = await a_scanned_invoice(
            client, settings, owner, customer_id=customer_id, imei=SECOND_IMEI
        )
        await confirm(
            client,
            owner,
            invoice_id,
            paymentType="credit_company",
            creditCompanyId=company_id,
        )

        refused = await tender(client, owner, invoice_id, "7620000")

        assert refused.status_code == 409, refused.text

    async def test_a_draft_takes_none(self, client, settings, owner):
        await keep_a_till(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner)

        refused = await tender(client, owner, invoice_id, "7620000")

        assert refused.status_code == 409, refused.text

    async def test_a_dollar_payment_on_a_debt_is_still_refused(
        self, client, settings, owner
    ):
        """§4.7 is untouched: a store-credit debt is som and only som pays
        it down, whatever currency the handset was priced in."""
        await keep_a_till(client, owner)
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(
            client, settings, owner, customer_id=customer_id
        )
        await confirm(
            client, owner, invoice_id, paymentType="store_credit", debt="7800000"
        )

        refused = await tender(client, owner, invoice_id, "600.00", currency="USD")

        assert refused.status_code == 422, refused.text


class TestTheAuditsStillReconcile:
    async def test_a_sale_tendered_in_two_currencies_reconciles(
        self, client, settings, owner, capsys
    ):
        """Regression: the balance audit summed one sale's payments across
        currencies and crashed on the first mixed tender it met."""
        await keep_a_till(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(client, owner, invoice_id)
        await tender(client, owner, invoice_id, "300.00", currency="USD")
        await tender(client, owner, invoice_id, "3810000")

        assert await _verify(settings, "verify-balances", None) == 0
        assert await _verify(settings, "verify-financials", None) == 0
        assert "everything reconciles" in capsys.readouterr().out

    async def test_a_tender_is_not_reported_as_money_against_no_debt(
        self, client, settings, owner, capsys
    ):
        """The audit's "a settled sale holds no payment" rule predates the
        tender; a paid-in-full sale is now allowed to hold one."""
        await keep_a_till(client, owner)
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(client, owner, invoice_id, tendered="7620000")

        assert await _verify(settings, "verify-balances", None) == 0
        assert "everything reconciles" in capsys.readouterr().out


class TestWithoutATillNothingChanges:
    """The default. A store that was never asked whether it balances a
    drawer sees exactly the system V1 shipped."""

    async def test_the_flag_is_off_until_somebody_turns_it_on(self, client, owner):
        read = await client.get(f"{API}/settings/tenant", headers=owner.auth)

        assert read.status_code == 200, read.text
        assert read.json()["data"]["runsTill"] is False

    async def test_a_tender_is_refused(self, client, settings, owner):
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(client, owner, invoice_id)

        refused = await tender(client, owner, invoice_id, "7620000")

        assert refused.status_code == 409, refused.text

    async def test_a_confirm_that_states_a_tender_is_refused_rather_than_ignored(
        self, client, settings, owner
    ):
        """Silently dropping the figure would be worse: the seller would
        think the till had it."""
        invoice_id = await a_scanned_invoice(client, settings, owner)

        refused = await client.post(
            f"{API}/invoices/{invoice_id}/confirm",
            headers=owner.auth,
            json={"tendered": "7620000"},
        )

        assert refused.status_code == 409, refused.text

    async def test_a_som_paid_trade_in_books_nothing_but_its_purchase(
        self, client, settings, owner
    ):
        """FR-3.4c holds while the till is off: the som handed to the
        walk-in is a note, and no ledger row equals it."""
        await a_trade_in(client, settings, owner, cost="330", cash="4200000")

        rows = await client.get(f"{API}/reports/financial-ledger", headers=owner.auth)
        booked = [
            (row["txnType"], row["amount"]["minor"]) for row in rows.json()["data"]
        ]

        assert ("purchase", -33000) in booked
        assert not [row for row in booked if row[0].startswith("tender")]
        assert not [row for row in booked if abs(row[1]) == 4_200_000]

    async def test_turning_the_till_on_books_what_leaves_the_drawer(
        self, client, settings, owner
    ):
        """The other half of the till: buying a handset takes cash out."""
        await keep_a_till(client, owner)

        await a_trade_in(client, settings, owner, cost="330", cash="4200000")

        rows = await client.get(f"{API}/reports/financial-ledger", headers=owner.auth)
        booked = [
            (row["txnType"], row["amount"]["minor"], row["amount"]["currency"])
            for row in rows.json()["data"]
        ]

        # The purchase is what the handset is worth, in the product's own
        # currency. The tender is the som that physically left the box.
        # Neither is derived from the other and no rate connects them.
        assert ("purchase", -33000, "USD") in booked
        assert ("tender_paid", -4_200_000, "UZS") in booked
