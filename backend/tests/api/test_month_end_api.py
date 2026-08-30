"""The month-end close over HTTP — FR-10.4 to FR-10.9, PRD §5.10.

The §10 demo, run against a real store: buy a phone into the warehouse,
sell one, and read the month back for the whole store and for one location.
What only a database can prove here is the two reconciliations — the
closing value against on-hand stock, and closing debt against customer
balances — because both recompute from the ledger with SQL the fakes only
approximate.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tests.api.ledger_helpers import PHONE_IMEI, receive_phone
from tests.api.pdf_helpers import pdf_text

API = "/api/v1"


async def this_month(client, auth) -> dict[str, int]:
    """The current month in the store's own timezone (FR-10.8) — the same
    boundary the report itself uses, so the demo cannot straddle one."""
    response = await client.get(f"{API}/settings/tenant", headers=auth)
    assert response.status_code == 200, response.text
    local = datetime.now(ZoneInfo(response.json()["data"]["timezone"]))
    return {"year": local.year, "month": local.month}


async def month_end(client, auth, **params):
    response = await client.get(f"{API}/reports/month-end", headers=auth, params=params)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def sell(client, owner, location_id, imei=PHONE_IMEI, customer_id=None, **terms):
    invoice = {"locationId": str(location_id)}
    if customer_id is not None:
        invoice["customerId"] = customer_id
    created = await client.post(f"{API}/invoices", headers=owner.auth, json=invoice)
    assert created.status_code == 201, created.text
    invoice_id = created.json()["data"]["id"]
    scanned = await client.post(
        f"{API}/invoices/{invoice_id}/scan", headers=owner.auth, json={"code": imei}
    )
    assert scanned.status_code == 200, scanned.text
    confirmed = await client.post(
        f"{API}/invoices/{invoice_id}/confirm", headers=owner.auth, json=terms or None
    )
    assert confirmed.status_code == 200, confirmed.text
    return invoice_id


async def a_priced_handset(client, settings, owner, imei=PHONE_IMEI):
    unit_id, product_id, location_id = await receive_phone(
        client, settings, owner, imei=imei
    )
    priced = await client.patch(
        f"{API}/device-units/{unit_id}/price",
        headers=owner.auth,
        json={"askingPrice": "600", "reason": "priced for sale"},
    )
    assert priced.status_code == 200, priced.text
    return unit_id, product_id, location_id


class TestTheCloseReadsBackWhatTheDocumentsWrote:
    async def test_a_phone_in_stock_is_the_closing_inventory_value(
        self, client, settings, owner
    ):
        await a_priced_handset(client, settings, owner)

        body = await month_end(client, owner.auth, **await this_month(client, owner.auth))

        assert _minor(body["figures"]["closingInventory"], "USD") == 38000
        assert _minor(body["figures"]["purchases"], "USD") == -38000

    async def test_selling_it_books_revenue_cogs_and_margin(
        self, client, settings, owner
    ):
        _, _, location_id = await a_priced_handset(client, settings, owner)
        await sell(client, owner, location_id)

        body = await month_end(client, owner.auth, **await this_month(client, owner.auth))

        assert _minor(body["figures"]["revenue"], "USD") == 60000
        assert _minor(body["figures"]["costOfGoods"], "USD") == -38000
        assert _minor(body["figures"]["margin"], "USD") == 22000
        assert _minor(body["figures"]["closingInventory"], "USD") == 0

    async def test_every_figure_is_per_currency_never_merged(
        self, client, settings, owner
    ):
        """FR-10.4: a USD column and a UZS column, side by side. There is no
        field on this payload a combined number could be written into."""
        await a_priced_handset(client, settings, owner)

        body = await month_end(client, owner.auth, **await this_month(client, owner.auth))

        for figure in body["figures"].values():
            assert isinstance(figure, list)

    async def test_the_period_is_stated_in_the_stores_own_timezone(
        self, client, owner
    ):
        body = await month_end(client, owner.auth, year=2026, month=1)

        assert body["period"]["timezone"] == "Asia/Tashkent"
        assert body["period"]["start"].startswith("2025-12-31T19:00")
        assert body["period"]["end"].startswith("2026-01-31T19:00")


class TestTheDemo:
    """§10: run last month for the warehouse and the store, and reconcile."""

    async def test_the_closing_value_reconciles_against_on_hand(
        self, client, settings, owner
    ):
        """FR-10.7: the money ledger's closing figure against stock, per
        currency, recomputed from the ledger rather than trusted."""
        await a_priced_handset(client, settings, owner)

        body = await month_end(client, owner.auth, **await this_month(client, owner.auth))

        assert body["reconciles"] is True
        assert body["discrepancies"] == []

    async def test_the_value_is_broken_down_by_where_it_sits(
        self, client, settings, owner
    ):
        """FR-10.6."""
        _, _, location_id = await a_priced_handset(client, settings, owner)

        body = await month_end(client, owner.auth, **await this_month(client, owner.auth))

        assert [row["locationId"] for row in body["closingByLocation"]] == [
            str(location_id)
        ]
        assert _minor(body["closingByLocation"][0]["value"], "USD") == 38000

    async def test_one_location_at_a_time(self, client, settings, owner):
        """FR-10.4: the same month for the shelf the goods are on, and for
        one they are not."""
        _, _, location_id = await a_priced_handset(client, settings, owner)
        elsewhere = await client.post(
            f"{API}/locations", headers=owner.auth, json={"name": "Warehouse"}
        )
        assert elsewhere.status_code == 201, elsewhere.text
        period = await this_month(client, owner.auth)

        here = await month_end(client, owner.auth, **period, locationId=str(location_id))
        there = await month_end(
            client, owner.auth, **period, locationId=elsewhere.json()["data"]["id"]
        )

        assert _minor(here["figures"]["closingInventory"], "USD") == 38000
        assert _minor(there["figures"]["closingInventory"], "USD") == 0
        assert there["closingByLocation"] == []

    async def test_closing_debt_reconciles_against_customer_balances(
        self, client, settings, owner
    ):
        """FR-10.7b: the debt movement has to land on what the customers
        actually owe, which is ``verify-balances`` run as part of the
        report."""
        _, _, location_id = await a_priced_handset(client, settings, owner)
        customer = await client.post(
            f"{API}/customers", headers=owner.auth, json={"fullName": "Aziz"}
        )
        assert customer.status_code == 201, customer.text
        await sell(
            client,
            owner,
            location_id,
            customer_id=customer.json()["data"]["id"],
            paymentType="store_credit",
            debt="7800000",
            downPayment="800000",
        )

        body = await month_end(client, owner.auth, **await this_month(client, owner.auth))

        assert body["debt"]["bookedMinor"] == 7_800_000
        assert body["debt"]["collectedMinor"] == 800_000
        assert body["debt"]["closingMinor"] == 7_000_000
        assert body["reconciles"] is True

    async def test_the_sale_is_labelled_by_how_it_was_financed(
        self, client, settings, owner
    ):
        """FR-10.5's last line."""
        _, _, location_id = await a_priced_handset(client, settings, owner)
        await sell(client, owner, location_id)

        body = await month_end(client, owner.auth, **await this_month(client, owner.auth))

        assert [row["paymentType"] for row in body["financing"]] == ["paid_in_full"]
        assert body["financing"][0]["invoiceCount"] == 1


class TestThePdf:
    async def test_the_close_downloads_as_a_pdf_naming_its_period(
        self, client, settings, owner
    ):
        """FR-10.9."""
        _, _, location_id = await a_priced_handset(client, settings, owner)
        await sell(client, owner, location_id)
        period = await this_month(client, owner.auth)

        response = await client.get(
            f"{API}/reports/month-end/pdf", headers=owner.auth, params=period
        )

        assert response.status_code == 200, response.text
        assert response.content.startswith(b"%PDF")
        text = pdf_text(response.content)
        assert "Month-End Report" in text
        assert "Gross margin" in text
        assert "Closing inventory" in text

    async def test_re_running_a_past_month_gives_the_same_bytes(
        self, client, settings, owner
    ):
        """FR-10.10: no figure is ever converted, and the creation date is
        pinned to the period's end rather than the clock, so the file is
        reproducible rather than merely consistent."""
        await a_priced_handset(client, settings, owner)

        first = await client.get(
            f"{API}/reports/month-end/pdf",
            headers=owner.auth,
            params={"year": 2026, "month": 1},
        )
        second = await client.get(
            f"{API}/reports/month-end/pdf",
            headers=owner.auth,
            params={"year": 2026, "month": 1},
        )

        assert first.content == second.content


class TestWhoMaySeeIt:
    @pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
    async def test_the_close_is_money_and_takes_the_ledger_permission(
        self, client, tenant_with_roles, role
    ):
        _, tokens, _ = tenant_with_roles

        allowed = await client.get(
            f"{API}/reports/month-end",
            headers=tokens["tenant.owner"],
            params={"year": 2026, "month": 1},
        )
        denied = await client.get(
            f"{API}/reports/month-end",
            headers=tokens[role],
            params={"year": 2026, "month": 1},
        )

        assert allowed.status_code == 200, allowed.text
        assert denied.status_code == 403

    async def test_a_manager_may_run_it(self, client, tenant_with_roles):
        _, tokens, _ = tenant_with_roles

        response = await client.get(
            f"{API}/reports/month-end",
            headers=tokens["tenant.manager"],
            params={"year": 2026, "month": 1},
        )

        assert response.status_code == 200, response.text

    @pytest.mark.parametrize("role", ["tenant.storekeeper", "tenant.seller"])
    async def test_the_pdf_is_gated_the_same_way(self, client, tenant_with_roles, role):
        _, tokens, _ = tenant_with_roles

        denied = await client.get(
            f"{API}/reports/month-end/pdf",
            headers=tokens[role],
            params={"year": 2026, "month": 1},
        )

        assert denied.status_code == 403


class TestARefusedPeriod:
    async def test_a_thirteenth_month_is_rejected(self, client, owner):
        response = await client.get(
            f"{API}/reports/month-end",
            headers=owner.auth,
            params={"year": 2026, "month": 13},
        )

        assert response.status_code == 422


def _minor(subtotals: list[dict], currency: str) -> int:
    """One currency's figure, or zero — never a total across the list."""
    for subtotal in subtotals:
        if subtotal["currency"] == currency:
            return subtotal["amountMinor"]
    return 0
