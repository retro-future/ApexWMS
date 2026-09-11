"""What the customer actually handed over on a sale settled at the counter.

The gap this closes: a $600 handset paid for in cash som booked revenue in
dollars and recorded no som figure anywhere, so a till could not be balanced
at the end of a shift. The tender is the som figure, sitting beside the
dollar revenue and never netted against it — there is still no rate in the
system, and the two numbers are two independent facts about one sale.

It is recorded for every store (W9 B1): a figure not written down at the
counter cannot be recovered afterwards. ``runsTill`` is left for the shift
screens B5 will build, and the last class here is that off state.
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


class TestTheCapOnTheAmount:
    """A tender owes nothing, so only the sale's own total can cap it."""

    async def test_more_than_the_sale_charges_is_refused(
        self, client, settings, owner
    ):
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(client, owner, invoice_id)

        refused = await tender(client, owner, invoice_id, "6000.00", currency="USD")

        assert refused.status_code == 409, refused.text

    async def test_a_som_tender_on_a_dollar_sale_is_not_capped(
        self, client, settings, owner
    ):
        """No rate is involved anywhere in this rule, so there is no som
        column to compare a som figure against."""
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(client, owner, invoice_id)

        taken = await tender(client, owner, invoice_id, "99000000")

        assert taken.status_code == 201, taken.text


class TestOneRowPerCurrency:
    """A tender has no cap, so the row count is the only thing guarding it."""

    async def test_a_second_som_row_is_refused(self, client, settings, owner):
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(client, owner, invoice_id)
        await tender(client, owner, invoice_id, "7620000")

        again = await tender(client, owner, invoice_id, "7620000")

        assert again.status_code == 409, again.text

    async def test_the_other_currency_is_still_free(self, client, settings, owner):
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(client, owner, invoice_id)
        await tender(client, owner, invoice_id, "3810000")

        rest = await tender(client, owner, invoice_id, "300.00", currency="USD")

        assert rest.status_code == 201, rest.text

    async def test_reversing_frees_the_currency_again(self, client, settings, owner):
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(client, owner, invoice_id)
        first = await tender(client, owner, invoice_id, "7000000")
        payment_id = first.json()["data"]["payments"][0]["id"]

        undone = await client.post(
            f"{API}/payments/{payment_id}/reverse", headers=owner.auth
        )
        assert undone.status_code == 200, undone.text

        corrected = await tender(client, owner, invoice_id, "7620000")

        assert corrected.status_code == 201, corrected.text

    async def test_a_down_payment_does_not_block_the_next_instalment(
        self, client, settings, owner
    ):
        """The rule is the tender's alone; a debt is paid down in instalments."""
        customer_id = await a_customer(client, owner)
        invoice_id = await a_scanned_invoice(
            client, settings, owner, customer_id=customer_id
        )
        await confirm(
            client,
            owner,
            invoice_id,
            paymentType="store_credit",
            debt="7620000",
            downPayment="1000000",
        )

        again = await tender(client, owner, invoice_id, "1000000")

        assert again.status_code == 201, again.text


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
    drawer still records what crossed its counter, and nothing else."""

    async def test_the_flag_is_off_until_somebody_turns_it_on(self, client, owner):
        read = await client.get(f"{API}/settings/tenant", headers=owner.auth)

        assert read.status_code == 200, read.text
        assert read.json()["data"]["runsTill"] is False

    async def test_a_tender_is_recorded_anyway(self, client, settings, owner):
        """W9 B1: the som a customer handed over is the only som figure a
        dollar-priced sale ever has, so it is written down whether or not
        the store balances a drawer."""
        invoice_id = await a_scanned_invoice(client, settings, owner)
        await confirm(client, owner, invoice_id)

        taken = await tender(client, owner, invoice_id, "7620000")

        assert taken.status_code == 201, taken.text
        assert taken.json()["data"]["tendered"] == [
            {"currency": "UZS", "minor": 7_620_000}
        ]

    async def test_a_confirm_that_states_a_tender_records_it(
        self, client, settings, owner
    ):
        invoice_id = await a_scanned_invoice(client, settings, owner)

        confirmed = await client.post(
            f"{API}/invoices/{invoice_id}/confirm",
            headers=owner.auth,
            json={"tendered": "7620000"},
        )

        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["data"]["tendered"] == [
            {"currency": "UZS", "minor": 7_620_000}
        ]

    async def test_a_som_paid_trade_in_books_the_payout_anyway(
        self, client, settings, owner
    ):
        """W9 B2, the buying side of B1's rule: the som handed to the
        walk-in is the only som figure the purchase ever has."""
        await a_trade_in(client, settings, owner, cost="330", cash="4200000")

        rows = await client.get(f"{API}/reports/financial-ledger", headers=owner.auth)
        booked = [
            (row["txnType"], row["amount"]["minor"], row["amount"]["currency"])
            for row in rows.json()["data"]
        ]

        assert ("purchase", -33000, "USD") in booked
        assert ("tender_paid", -4_200_000, "UZS") in booked

    async def test_the_till_changes_nothing_about_the_payout(
        self, client, settings, owner
    ):
        """The flag now gates the shift screens, not the recording."""
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
