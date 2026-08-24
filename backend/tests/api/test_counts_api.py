"""M6's demo, against a real tenant database (PRD §10).

*"Hide a phone, run a count, watch the system find it missing and book the
loss."*

Everything here goes through HTTP. Nothing reaches into a repository, so
what passes is the surface a storekeeper with a keyboard-wedge scanner
actually drives — including the part that matters most, that the count and
the confirm are done by two different people (FR-6.4).
"""

import pytest

from tests.api.ledger_helpers import PASSWORD

API = "/api/v1"

# Fifteen digits with a valid Luhn check digit.
SHELF_IMEIS = ["490154203237518", "356938035643809", "352099001761481"]
# The one the store has never heard of — FR-6.4b's surprise.
UNKNOWN_IMEI = "013269009999992"


@pytest.fixture
async def store(client, create_tenant):
    """A store with two phones and a box of cases actually in stock."""
    owner = await create_tenant(password=PASSWORD)

    async def post(path: str, body: dict) -> dict:
        response = await client.post(f"{API}{path}", headers=owner.auth, json=body)
        assert response.status_code == 201, response.text
        return response.json()["data"]

    location = await post("/locations", {"name": "Chilonzor shop"})
    supplier = await post("/suppliers", {"name": "Tashkent Mobile"})
    phone = await post(
        "/products",
        {
            "sku": "IP15P-256",
            "name": "iPhone 15 Pro 256GB",
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
            "trackingType": "quantity",
            "currency": "UZS",
            "defaultSalePrice": "50000",
        },
    )

    receipt = await post(
        "/receipts",
        {
            "locationId": location["id"],
            "acquisitionSource": "supplier",
            "supplierId": supplier["id"],
            "lines": [
                {"productId": phone["id"], "quantity": 3},
                {"productId": case["id"], "quantity": 10, "unitCost": "30000"},
            ],
        },
    )
    for imei in SHELF_IMEIS:
        scanned = await client.post(
            f"{API}/receipts/{receipt['id']}/scan",
            headers=owner.auth,
            json={"imei": imei, "acquisitionCost": "700.00"},
        )
        assert scanned.status_code == 200, scanned.text
    confirmed = await client.post(
        f"{API}/receipts/{receipt['id']}/confirm", headers=owner.auth, json={}
    )
    assert confirmed.status_code == 200, confirmed.text

    return owner, {
        "location": location["id"],
        "supplier": supplier["id"],
        "phone": phone["id"],
        "case": case["id"],
    }


async def open_count(client, auth, location_id: str) -> dict:
    response = await client.post(
        f"{API}/stock-counts", headers=auth, json={"locationId": location_id}
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def scan(client, auth, count_id: str, code: str, **fields):
    return await client.post(
        f"{API}/stock-counts/{count_id}/scan",
        headers=auth,
        json={"code": code, **fields},
    )


async def unit_by_imei(client, auth, imei: str) -> dict:
    found = await client.get(f"{API}/scan/lookup", headers=auth, params={"code": imei})
    assert found.status_code == 200, found.text
    return found.json()["data"]["device"]


class TestTheDemo:
    async def test_hide_a_phone_and_the_count_finds_it_missing(self, client, store):
        owner, ids = store

        count = await open_count(client, owner.auth, ids["location"])
        assert count["number"].startswith("SC-")
        # The snapshot: three handsets and one accessory line (FR-6.1).
        assert len(count["units"]) == 3
        assert len(count["lines"]) == 1

        # Two are on the shelf. The third has walked.
        for imei in SHELF_IMEIS[:2]:
            beeped = await scan(client, owner.auth, count["id"], imei)
            assert beeped.status_code == 200, beeped.text
        await client.patch(
            f"{API}/stock-counts/{count['id']}/lines/{count['lines'][0]['id']}",
            headers=owner.auth,
            json={"countedQuantity": 10},
        )

        closed = await client.post(
            f"{API}/stock-counts/{count['id']}/close", headers=owner.auth, json={}
        )
        assert closed.status_code == 200, closed.text
        report = closed.json()["data"]
        assert report["matchedCount"] == 2
        assert report["missingCount"] == 1
        assert report["unexpectedCount"] == 0

        missing = [u for u in report["units"] if u["outcome"] == "missing"]
        assert [u["imei"] for u in missing] == [SHELF_IMEIS[2]]

        confirmed = await client.post(
            f"{API}/stock-counts/{count['id']}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["data"]["status"] == "confirmed"

        gone = await unit_by_imei(client, owner.auth, SHELF_IMEIS[2])
        assert gone["status"] == "written_off"

    async def test_an_accessory_shortage_is_adjusted_too(self, client, store):
        """FR-6.2: the shelf of cases is counted by eye and entered."""
        owner, ids = store
        count = await open_count(client, owner.auth, ids["location"])
        for imei in SHELF_IMEIS:
            await scan(client, owner.auth, count["id"], imei)

        line = count["lines"][0]
        assert line["expectedQuantity"] == 10
        await client.patch(
            f"{API}/stock-counts/{count['id']}/lines/{line['id']}",
            headers=owner.auth,
            json={"countedQuantity": 8},
        )
        closed = await client.post(
            f"{API}/stock-counts/{count['id']}/close", headers=owner.auth, json={}
        )
        assert closed.json()["data"]["lines"][0]["delta"] == -2

        confirmed = await client.post(
            f"{API}/stock-counts/{count['id']}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text


class TestTheCountAndTheConfirmAreDifferentPeople:
    """FR-6.4, §2.1: a Storekeeper reports, an Owner or Manager agrees."""

    @pytest.fixture
    async def storekeeper(self, client, store):
        owner, ids = store
        invite = await client.post(
            f"{API}/users/invite",
            headers=owner.auth,
            json={"email": "keeper@example.com", "role": "tenant.storekeeper"},
        )
        assert invite.status_code == 201, invite.text
        accepted = await client.post(
            f"{API}/auth/accept-invite",
            json={"token": invite.json()["data"]["token"], "password": "keeperpass1"},
        )
        assert accepted.status_code == 201, accepted.text
        login = await client.post(
            f"{API}/auth/login",
            json={"email": "keeper@example.com", "password": "keeperpass1"},
        )
        assert login.status_code == 200, login.text
        token = login.json()["data"]["accessToken"]
        return {"Authorization": f"Bearer {token}"}, owner, ids

    async def test_a_storekeeper_opens_scans_and_closes(self, client, storekeeper):
        auth, _, ids = storekeeper

        count = await open_count(client, auth, ids["location"])
        beeped = await scan(client, auth, count["id"], SHELF_IMEIS[0])
        assert beeped.status_code == 200, beeped.text

        closed = await client.post(
            f"{API}/stock-counts/{count['id']}/close", headers=auth, json={}
        )
        assert closed.status_code == 200, closed.text

    async def test_but_may_not_confirm_the_adjustments(self, client, storekeeper):
        auth, _, ids = storekeeper
        count = await open_count(client, auth, ids["location"])
        await scan(client, auth, count["id"], SHELF_IMEIS[0])
        await client.post(f"{API}/stock-counts/{count['id']}/close", headers=auth, json={})

        refused = await client.post(
            f"{API}/stock-counts/{count['id']}/confirm", headers=auth, json={}
        )

        assert refused.status_code == 403

    async def test_and_a_403_adjusts_nothing(self, client, storekeeper):
        auth, owner, ids = storekeeper
        count = await open_count(client, auth, ids["location"])
        await client.post(f"{API}/stock-counts/{count['id']}/close", headers=auth, json={})
        await client.post(f"{API}/stock-counts/{count['id']}/confirm", headers=auth, json={})

        still_here = await unit_by_imei(client, owner.auth, SHELF_IMEIS[0])
        assert still_here["status"] == "in_stock"

    async def test_a_storekeeper_may_not_state_what_a_surprise_cost(
        self, client, storekeeper
    ):
        """``Pricing.Set`` escalates the scan, exactly as it does on a
        receipt: stating money is not a stockroom act (§2.1)."""
        auth, _, ids = storekeeper
        count = await open_count(client, auth, ids["location"])

        refused = await scan(
            client,
            auth,
            count["id"],
            UNKNOWN_IMEI,
            productId=ids["phone"],
            acquisitionCost="300.00",
        )

        assert refused.status_code == 403

    async def test_but_may_scan_it_and_leave_the_cost_to_somebody_else(
        self, client, storekeeper
    ):
        auth, owner, ids = storekeeper
        count = await open_count(client, auth, ids["location"])

        beeped = await scan(client, auth, count["id"], UNKNOWN_IMEI, productId=ids["phone"])

        assert beeped.status_code == 200, beeped.text
        assert beeped.json()["data"]["unit"]["outcome"] == "unexpected"
        assert beeped.json()["data"]["unit"]["isSurprise"] is True

    async def test_the_storekeepers_report_carries_no_costs(self, client, storekeeper):
        """FR-1.7: they run the count and never see what stock cost."""
        auth, owner, ids = storekeeper
        count = await open_count(client, auth, ids["location"])
        await scan(
            client,
            owner.auth,
            count["id"],
            UNKNOWN_IMEI,
            productId=ids["phone"],
            acquisitionCost="300.00",
        )

        read = await client.get(f"{API}/stock-counts/{count['id']}", headers=auth)

        assert read.status_code == 200, read.text
        surprise = [u for u in read.json()["data"]["units"] if u["isSurprise"]][0]
        assert surprise["acquisitionCost"] is None
        # The report itself is still fully readable.
        assert surprise["outcome"] == "unexpected"


class TestASurpriseHandsetIsUnsellableUntilPriced:
    """FR-6.4b's own test: refused for want of a price, **not** quoted the
    catalog's new-goods figure."""

    async def test_confirming_a_count_that_found_one_creates_it(self, client, store):
        owner, ids = store
        count = await open_count(client, owner.auth, ids["location"])
        for imei in SHELF_IMEIS:
            await scan(client, owner.auth, count["id"], imei)
        await scan(
            client,
            owner.auth,
            count["id"],
            UNKNOWN_IMEI,
            productId=ids["phone"],
            acquisitionCost="300.00",
        )
        await client.patch(
            f"{API}/stock-counts/{count['id']}/lines/{count['lines'][0]['id']}",
            headers=owner.auth,
            json={"countedQuantity": 10},
        )
        await client.post(
            f"{API}/stock-counts/{count['id']}/close", headers=owner.auth, json={}
        )

        confirmed = await client.post(
            f"{API}/stock-counts/{count['id']}/confirm", headers=owner.auth, json={}
        )

        assert confirmed.status_code == 200, confirmed.text
        found = await unit_by_imei(client, owner.auth, UNKNOWN_IMEI)
        assert found["status"] == "in_stock"
        assert found["condition"] == "used"
        assert found["askingPrice"] is None

    async def test_and_the_counter_refuses_to_sell_it(self, client, store):
        owner, ids = store
        count = await open_count(client, owner.auth, ids["location"])
        for imei in SHELF_IMEIS:
            await scan(client, owner.auth, count["id"], imei)
        await scan(
            client,
            owner.auth,
            count["id"],
            UNKNOWN_IMEI,
            productId=ids["phone"],
            acquisitionCost="300.00",
        )
        await client.patch(
            f"{API}/stock-counts/{count['id']}/lines/{count['lines'][0]['id']}",
            headers=owner.auth,
            json={"countedQuantity": 10},
        )
        await client.post(
            f"{API}/stock-counts/{count['id']}/close", headers=owner.auth, json={}
        )
        await client.post(
            f"{API}/stock-counts/{count['id']}/confirm", headers=owner.auth, json={}
        )

        invoice = await client.post(
            f"{API}/invoices", headers=owner.auth, json={"locationId": ids["location"]}
        )
        assert invoice.status_code == 201, invoice.text
        refused = await client.post(
            f"{API}/invoices/{invoice.json()['data']['id']}/scan",
            headers=owner.auth,
            json={"code": UNKNOWN_IMEI},
        )

        assert refused.status_code == 409
        detail = refused.json()["detail"]
        # No figure is quoted, least of all the catalog's $900, and the
        # message names who can fix it (§2.1).
        assert "$900" not in detail
        assert "never inherits the catalog price" in detail
        assert "Owner or Manager" in detail

    async def test_a_surprise_with_no_cost_blocks_the_confirm(self, client, store):
        owner, ids = store
        count = await open_count(client, owner.auth, ids["location"])
        for imei in SHELF_IMEIS:
            await scan(client, owner.auth, count["id"], imei)
        await scan(client, owner.auth, count["id"], UNKNOWN_IMEI, productId=ids["phone"])
        await client.post(
            f"{API}/stock-counts/{count['id']}/close", headers=owner.auth, json={}
        )

        refused = await client.post(
            f"{API}/stock-counts/{count['id']}/confirm", headers=owner.auth, json={}
        )

        assert refused.status_code == 422
        assert UNKNOWN_IMEI in refused.json()["detail"]


class TestClosingIsASeparateAct:
    async def test_confirming_before_closing_is_a_conflict(self, client, store):
        owner, ids = store
        count = await open_count(client, owner.auth, ids["location"])

        refused = await client.post(
            f"{API}/stock-counts/{count['id']}/confirm", headers=owner.auth, json={}
        )

        assert refused.status_code == 409

    async def test_scanning_after_closing_is_a_conflict(self, client, store):
        owner, ids = store
        count = await open_count(client, owner.auth, ids["location"])
        await scan(client, owner.auth, count["id"], SHELF_IMEIS[0])
        await client.post(
            f"{API}/stock-counts/{count['id']}/close", headers=owner.auth, json={}
        )

        refused = await scan(client, owner.auth, count["id"], SHELF_IMEIS[1])

        assert refused.status_code == 409

    async def test_a_closed_count_is_still_a_draft(self, client, store):
        owner, ids = store
        count = await open_count(client, owner.auth, ids["location"])
        await scan(client, owner.auth, count["id"], SHELF_IMEIS[0])

        closed = await client.post(
            f"{API}/stock-counts/{count['id']}/close", headers=owner.auth, json={}
        )

        data = closed.json()["data"]
        assert data["status"] == "draft"
        assert data["closedAt"] is not None


class TestCancellingACount:
    async def test_a_handset_written_off_by_a_count_comes_back(self, client, store):
        owner, ids = store
        count = await open_count(client, owner.auth, ids["location"])
        for imei in SHELF_IMEIS[:2]:
            await scan(client, owner.auth, count["id"], imei)
        await client.patch(
            f"{API}/stock-counts/{count['id']}/lines/{count['lines'][0]['id']}",
            headers=owner.auth,
            json={"countedQuantity": 10},
        )
        await client.post(
            f"{API}/stock-counts/{count['id']}/close", headers=owner.auth, json={}
        )
        await client.post(
            f"{API}/stock-counts/{count['id']}/confirm", headers=owner.auth, json={}
        )

        cancelled = await client.post(
            f"{API}/stock-counts/{count['id']}/cancel",
            headers=owner.auth,
            json={"reason": "the phone was in the safe"},
        )

        assert cancelled.status_code == 200, cancelled.text
        back = await unit_by_imei(client, owner.auth, SHELF_IMEIS[2])
        assert back["status"] == "in_stock"
