"""FR-9.1's stock-on-hand report, against real tables — PRD §5.9.

The report is the one place the two tracking types meet (§4.6): handsets
priced by specific identification, accessories by a weighted-average pool
replayed from the ledger. What these tests pin down is that they meet
without merging — a shelf holding $700 of phones and 300 000 som of cases
reports two figures, never their sum.
"""

import pytest

from tests.api.ledger_helpers import PASSWORD

API = "/api/v1"
PHONE_IMEI = "490154203237518"
SECOND_IMEI = "356938035643809"


@pytest.fixture
async def store(client, create_tenant):
    """Two locations, a USD phone and a UZS accessory, nothing received."""
    owner = await create_tenant(password=PASSWORD)

    async def post(path: str, body: dict) -> dict:
        response = await client.post(f"{API}{path}", headers=owner.auth, json=body)
        assert response.status_code == 201, response.text
        return response.json()["data"]

    shop = await post("/locations", {"name": "Chilonzor shop"})
    depot = await post("/locations", {"name": "Warehouse"})
    supplier = await post("/suppliers", {"name": "Tashkent Mobile"})
    phone = await post(
        "/products",
        {
            "sku": "IP15P-256",
            "name": "iPhone 15 Pro",
            "brand": "Apple",
            "trackingType": "serial",
            "currency": "USD",
            "defaultSalePrice": "900.00",
        },
    )
    case = await post(
        "/products",
        {
            "sku": "CASE-SIL-1",
            "name": "Silicone case",
            "brand": "Generic",
            "trackingType": "quantity",
            "currency": "UZS",
        },
    )
    return owner, {
        "shop": shop["id"],
        "depot": depot["id"],
        "supplier": supplier["id"],
        "phone": phone["id"],
        "case": case["id"],
    }


async def receive(client, owner, ids, location, lines, imeis=(), cost="700.00"):
    opened = await client.post(
        f"{API}/receipts",
        headers=owner.auth,
        json={
            "locationId": location,
            "acquisitionSource": "supplier",
            "supplierId": ids["supplier"],
            "lines": lines,
        },
    )
    assert opened.status_code == 201, opened.text
    receipt_id = opened.json()["data"]["id"]
    for imei in imeis:
        scanned = await client.post(
            f"{API}/receipts/{receipt_id}/scan",
            headers=owner.auth,
            json={"imei": imei, "acquisitionCost": cost},
        )
        assert scanned.status_code == 200, scanned.text
    confirmed = await client.post(
        f"{API}/receipts/{receipt_id}/confirm", headers=owner.auth, json={}
    )
    assert confirmed.status_code == 200, confirmed.text


async def on_hand(client, auth, **params):
    response = await client.get(
        f"{API}/reports/stock-on-hand", headers=auth, params=params
    )
    assert response.status_code == 200, response.text
    return response.json()


def subtotals(row):
    return {one["currency"]: one["amountMinor"] for one in row["costValue"]}


async def a_phone_on_the_shelf(client, owner, ids):
    await receive(
        client,
        owner,
        ids,
        ids["shop"],
        [{"productId": ids["phone"], "quantity": 1}],
        imeis=[PHONE_IMEI],
    )


async def a_second_phone_in_the_warehouse(client, owner, ids, cost="700.00"):
    await receive(
        client,
        owner,
        ids,
        ids["depot"],
        [{"productId": ids["phone"], "quantity": 1}],
        imeis=[SECOND_IMEI],
        cost=cost,
    )


async def a_mixed_shelf(client, owner, ids):
    await receive(
        client,
        owner,
        ids,
        ids["shop"],
        [
            {"productId": ids["phone"], "quantity": 1},
            {"productId": ids["case"], "quantity": 10, "unitCost": "30000"},
        ],
        imeis=[PHONE_IMEI],
    )


class TestTheTwoTrackingTypesMeetWithoutMerging:
    async def test_one_shelf_reports_a_usd_figure_and_a_uzs_figure(self, client, store):
        owner, ids = store
        await a_mixed_shelf(client, owner, ids)

        body = await on_hand(client, owner.auth, groupBy="location")

        assert body["totalItems"] == 1
        row = body["data"][0]
        assert row["label"] == "Chilonzor shop"
        assert row["key"] == ids["shop"]
        # One handset plus ten cases: eleven things on that shelf.
        assert row["quantity"] == 11
        assert subtotals(row) == {"USD": 70000, "UZS": 300000}

    async def test_no_field_anywhere_holds_their_sum(self, client, store):
        """FR-2.11: the payload has nowhere to put a combined figure."""
        owner, ids = store
        await a_mixed_shelf(client, owner, ids)

        row = (await on_hand(client, owner.auth, groupBy="location"))["data"][0]

        assert set(row) == {"groupBy", "key", "label", "quantity", "costValue"}
        assert len(row["costValue"]) == 2


class TestGrouping:
    async def test_by_location_separates_the_shelf_from_the_warehouse(
        self, client, store
    ):
        owner, ids = store
        await a_phone_on_the_shelf(client, owner, ids)
        await a_second_phone_in_the_warehouse(client, owner, ids, cost="650.00")

        body = await on_hand(client, owner.auth, groupBy="location")

        rows = {row["label"]: row for row in body["data"]}
        assert subtotals(rows["Chilonzor shop"]) == {"USD": 70000}
        assert subtotals(rows["Warehouse"]) == {"USD": 65000}

    async def test_by_product_totals_the_model_across_locations(self, client, store):
        owner, ids = store
        await a_phone_on_the_shelf(client, owner, ids)
        await a_second_phone_in_the_warehouse(client, owner, ids, cost="650.00")

        body = await on_hand(client, owner.auth, groupBy="product")

        assert body["totalItems"] == 1
        row = body["data"][0]
        assert row["label"] == "iPhone 15 Pro"
        assert row["sku"] == "IP15P-256"
        assert row["quantity"] == 2
        assert subtotals(row) == {"USD": 135000}

    async def test_the_sku_rides_along_only_when_grouping_by_product(
        self, client, store
    ):
        owner, ids = store
        await a_phone_on_the_shelf(client, owner, ids)

        by_location = (await on_hand(client, owner.auth, groupBy="location"))["data"][0]
        by_product = (await on_hand(client, owner.auth, groupBy="product"))["data"][0]

        assert "sku" not in by_location
        assert by_product["sku"] == "IP15P-256"

    async def test_by_brand_groups_on_the_free_text_column(self, client, store):
        owner, ids = store
        await a_mixed_shelf(client, owner, ids)

        body = await on_hand(client, owner.auth, groupBy="brand")

        rows = {row["label"]: row for row in body["data"]}
        assert subtotals(rows["Apple"]) == {"USD": 70000}
        assert subtotals(rows["Generic"]) == {"UZS": 300000}


class TestWhatLeavesTheReport:
    async def test_a_sold_handset_stops_counting(self, client, store):
        owner, ids = store
        await a_phone_on_the_shelf(client, owner, ids)
        created = await client.post(
            f"{API}/invoices", headers=owner.auth, json={"locationId": ids["shop"]}
        )
        invoice_id = created.json()["data"]["id"]
        await client.post(
            f"{API}/invoices/{invoice_id}/scan",
            headers=owner.auth,
            json={"code": PHONE_IMEI},
        )
        confirmed = await client.post(
            f"{API}/invoices/{invoice_id}/confirm", headers=owner.auth
        )
        assert confirmed.status_code == 200, confirmed.text

        assert (await on_hand(client, owner.auth))["totalItems"] == 0

    async def test_an_empty_store_reports_nothing_rather_than_zero(self, client, store):
        owner, _ = store

        body = await on_hand(client, owner.auth)

        assert body["totalItems"] == 0
        assert body["data"] == []


class TestFiltering:
    async def test_one_location_narrows_the_report_to_it(self, client, store):
        owner, ids = store
        await a_phone_on_the_shelf(client, owner, ids)
        await a_second_phone_in_the_warehouse(client, owner, ids)

        body = await on_hand(
            client, owner.auth, groupBy="product", locationId=ids["shop"]
        )

        assert body["data"][0]["quantity"] == 1


class TestWhoMayRead:
    async def test_a_seller_is_refused(self, client, store):
        owner, _ = store
        invite = await client.post(
            f"{API}/users/invite",
            headers=owner.auth,
            json={"email": "seller@example.com", "role": "tenant.seller"},
        )
        await client.post(
            f"{API}/auth/accept-invite",
            json={"token": invite.json()["data"]["token"], "password": "sellerpass1"},
        )
        login = await client.post(
            f"{API}/auth/login",
            json={"email": "seller@example.com", "password": "sellerpass1"},
        )
        seller = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}

        refused = await client.get(f"{API}/reports/stock-on-hand", headers=seller)

        assert refused.status_code == 403
