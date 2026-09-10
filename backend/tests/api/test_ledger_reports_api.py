"""The two raw ledger logs — FR-9.5 and FR-10.3, PRD §5.9, §5.10.

The pair exists so a confirm can be read back from both sides: goods in one
log, money in the other, written in the same transaction (FR-10.1). What
these tests pin down is that both name the document an operator would
recognise, both name the person, and a cancellation appears twice rather
than disappearing once.
"""

from tests.api.ledger_helpers import PASSWORD, PHONE_IMEI, receive_phone

API = "/api/v1"


async def movements(client, auth, **params):
    response = await client.get(f"{API}/reports/movements", headers=auth, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def ledger(client, auth, **params):
    response = await client.get(
        f"{API}/reports/financial-ledger", headers=auth, params=params
    )
    assert response.status_code == 200, response.text
    return response.json()


async def sell(client, owner, location_id, imei=PHONE_IMEI):
    created = await client.post(
        f"{API}/invoices", headers=owner.auth, json={"locationId": str(location_id)}
    )
    invoice_id = created.json()["data"]["id"]
    scanned = await client.post(
        f"{API}/invoices/{invoice_id}/scan", headers=owner.auth, json={"code": imei}
    )
    assert scanned.status_code == 200, scanned.text
    confirmed = await client.post(
        f"{API}/invoices/{invoice_id}/confirm", headers=owner.auth
    )
    assert confirmed.status_code == 200, confirmed.text
    return invoice_id, confirmed.json()["data"]["number"]


async def a_priced_handset(client, settings, owner):
    unit_id, product_id, location_id = await receive_phone(client, settings, owner)
    priced = await client.patch(
        f"{API}/device-units/{unit_id}/price",
        headers=owner.auth,
        json={"askingPrice": "500", "reason": "priced for sale"},
    )
    assert priced.status_code == 200, priced.text
    return unit_id, product_id, location_id


class TestTheMovementLog:
    async def test_a_receipt_appears_with_its_handset_place_and_person(
        self, client, settings, owner
    ):
        unit_id, product_id, location_id = await receive_phone(
            client, settings, owner
        )

        body = await movements(client, owner.auth)

        assert body["totalItems"] == 1
        row = body["data"][0]
        assert row["movementType"] == "receipt"
        assert row["quantityDelta"] == 1
        assert row["deviceUnitId"] == str(unit_id)
        assert row["imei"] == PHONE_IMEI
        assert row["productId"] == str(product_id)
        assert row["productName"] == "iPhone 15 Pro"
        assert row["locationId"] == str(location_id)
        assert row["locationName"]
        assert row["userId"] == owner.user_id
        assert row["userName"] == owner.full_name

    async def test_a_sale_is_a_negative_delta_naming_its_invoice(
        self, client, settings, owner
    ):
        _, _, location_id = await a_priced_handset(client, settings, owner)

        _, number = await sell(client, owner, location_id)

        rows = (await movements(client, owner.auth, movementType="sale"))["data"]
        assert len(rows) == 1
        assert rows[0]["quantityDelta"] == -1
        assert rows[0]["documentType"] == "sales_invoice"
        assert rows[0]["documentNumber"] == number

    async def test_a_cancellation_appears_beside_what_it_reverses(
        self, client, settings, owner
    ):
        """§4.3 rule 3: a reversal keeps its type and flips its sign, so the
        log has no category to exclude and the deltas net to zero."""
        _, _, location_id = await a_priced_handset(client, settings, owner)
        invoice_id, _ = await sell(client, owner, location_id)

        cancelled = await client.post(
            f"{API}/invoices/{invoice_id}/cancel", headers=owner.auth, json={}
        )
        assert cancelled.status_code == 200, cancelled.text

        rows = (await movements(client, owner.auth, movementType="sale"))["data"]
        assert len(rows) == 2
        assert sum(row["quantityDelta"] for row in rows) == 0


class TestMovementFiltering:
    async def test_one_handset_narrows_the_log_to_its_own_history(
        self, client, settings, owner
    ):
        unit_id, _, _ = await receive_phone(client, settings, owner)
        await receive_phone(
            client, settings, owner, imei="356938035643809"
        )

        body = await movements(client, owner.auth, deviceUnitId=str(unit_id))

        assert body["totalItems"] == 1
        assert body["data"][0]["imei"] == PHONE_IMEI

    async def test_a_type_nobody_wrote_matches_nothing(self, client, settings, owner):
        await receive_phone(client, settings, owner)

        assert (await movements(client, owner.auth, movementType="write_off"))[
            "totalItems"
        ] == 0


class TestTheFinancialLedger:
    async def test_a_purchase_is_booked_negative_in_the_products_currency(
        self, client, settings, owner
    ):
        await receive_phone(client, settings, owner, cost="380")

        body = await ledger(client, owner.auth)

        assert body["totalItems"] == 1
        row = body["data"][0]
        assert row["txnType"] == "purchase"
        assert row["amount"]["currency"] == "USD"
        # §4.6's sign convention describes cash: money left the till.
        assert row["amount"]["minor"] == -38000
        assert row["userName"] == owner.full_name

    async def test_a_confirmed_sale_books_revenue_and_cogs_against_its_invoice(
        self, client, settings, owner
    ):
        _, _, location_id = await a_priced_handset(client, settings, owner)

        _, number = await sell(client, owner, location_id)

        rows = (await ledger(client, owner.auth))["data"]
        booked = {row["txnType"]: row for row in rows}
        assert booked["sale_revenue"]["amount"]["minor"] == 50000
        assert booked["cogs"]["amount"]["minor"] == -38000
        assert booked["sale_revenue"]["documentNumber"] == number
        assert booked["sale_revenue"]["imei"] == PHONE_IMEI

    async def test_the_report_carries_no_total_of_any_kind(
        self, client, settings, owner
    ):
        """FR-2.11: these rows mix currencies by design, so the log has
        nowhere a single figure over them could be written."""
        await receive_phone(client, settings, owner)

        body = await ledger(client, owner.auth)

        assert set(body) == {
            "success",
            "message",
            "error",
            "data",
            "pageIndex",
            "pageSize",
            "pagesCount",
            "totalItems",
        }

    async def test_filtering_by_category_narrows_it(self, client, settings, owner):
        _, _, location_id = await a_priced_handset(client, settings, owner)
        await sell(client, owner, location_id)

        body = await ledger(client, owner.auth, txnType="cogs")

        assert body["totalItems"] == 1
        assert body["data"][0]["txnType"] == "cogs"


class TestWhoMayRead:
    """§2.1 grades the two logs the same way today, but the money one takes
    ``FinancialLedger.View`` because the catalog grades them apart."""

    async def test_a_seller_is_refused_both(self, client, settings, owner):
        invite = await client.post(
            f"{API}/users/invite",
            headers=owner.auth,
            json={"email": "seller@example.com", "role": "tenant.seller"},
        )
        await client.post(
            f"{API}/auth/accept-invite",
            json={"token": invite.json()["data"]["token"], "password": PASSWORD},
        )
        login = await client.post(
            f"{API}/auth/login",
            json={"email": "seller@example.com", "password": PASSWORD},
        )
        seller = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}

        assert (
            await client.get(f"{API}/reports/movements", headers=seller)
        ).status_code == 403
        assert (
            await client.get(f"{API}/reports/financial-ledger", headers=seller)
        ).status_code == 403


async def summary(client, auth, **params):
    response = await client.get(
        f"{API}/reports/sales-summary", headers=auth, params=params
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def per_currency(figures, field):
    return {one["currency"]: one["minor"] for one in figures[field]}


class TestTheSalesSummary:
    async def test_one_sale_reports_units_revenue_cost_and_margin(
        self, client, settings, owner
    ):
        _, _, location_id = await a_priced_handset(client, settings, owner)
        await sell(client, owner, location_id)

        data = await summary(client, owner.auth)

        assert len(data["locations"]) == 1
        figures = data["locations"][0]["figures"]
        assert figures["unitsSold"] == 1
        assert per_currency(figures, "revenue") == {"USD": 50000}
        # §4.6's sign describes cash: the goods left, so cost is negative.
        assert per_currency(figures, "costOfGoods") == {"USD": -38000}
        assert per_currency(figures, "margin") == {"USD": 12000}

    async def test_the_store_total_repeats_the_only_location(
        self, client, settings, owner
    ):
        _, _, location_id = await a_priced_handset(client, settings, owner)
        await sell(client, owner, location_id)

        data = await summary(client, owner.auth)

        assert data["total"]["unitsSold"] == 1
        assert per_currency(data["total"], "margin") == {"USD": 12000}

    async def test_a_cancelled_sale_nets_out_of_every_figure(
        self, client, settings, owner
    ):
        """§4.3 rule 3 again: the reversal is the same categories negated,
        so nothing here has a category to exclude."""
        _, _, location_id = await a_priced_handset(client, settings, owner)
        invoice_id, _ = await sell(client, owner, location_id)

        cancelled = await client.post(
            f"{API}/invoices/{invoice_id}/cancel", headers=owner.auth, json={}
        )
        assert cancelled.status_code == 200, cancelled.text

        data = await summary(client, owner.auth)

        assert data["total"]["unitsSold"] == 0
        assert per_currency(data["total"], "revenue") == {"USD": 0}
        assert per_currency(data["total"], "margin") == {"USD": 0}

    async def test_a_window_before_the_sale_reports_nothing(
        self, client, settings, owner
    ):
        _, _, location_id = await a_priced_handset(client, settings, owner)
        await sell(client, owner, location_id)

        data = await summary(client, owner.auth, toDate="2020-01-01T00:00:00Z")

        assert data["locations"] == []
        assert data["total"]["unitsSold"] == 0
        assert data["total"]["revenue"] == []

    async def test_no_field_holds_a_combined_figure(self, client, settings, owner):
        """FR-2.11: every money field is a list of per-currency subtotals."""
        _, _, location_id = await a_priced_handset(client, settings, owner)
        await sell(client, owner, location_id)

        figures = (await summary(client, owner.auth))["total"]

        assert set(figures) == {
            "unitsSold",
            "revenue",
            "costOfGoods",
            "returns",
            "margin",
        }
        for field in ("revenue", "costOfGoods", "returns", "margin"):
            assert isinstance(figures[field], list)

    async def test_a_seller_is_refused(self, client, settings, owner):
        invite = await client.post(
            f"{API}/users/invite",
            headers=owner.auth,
            json={"email": "clerk@example.com", "role": "tenant.seller"},
        )
        await client.post(
            f"{API}/auth/accept-invite",
            json={"token": invite.json()["data"]["token"], "password": PASSWORD},
        )
        login = await client.post(
            f"{API}/auth/login",
            json={"email": "clerk@example.com", "password": PASSWORD},
        )
        seller = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}

        refused = await client.get(f"{API}/reports/sales-summary", headers=seller)

        assert refused.status_code == 403
