"""M8's demo, against a real tenant database — FR-9.2, PRD §10.

*"Trace one IMEI's entire life: bought, priced, cut twice, sold below
asking, with the name of whoever approved that."*

The handset in the first test is §5.9's own example: traded in from a
walk-in for 4 200 000 som and booked at $330, priced at $420, cut to $390
then $360, sold at $350. Every one of those events has to appear, in order,
on one timeline, with the som figure beside the booked cost and in no
total.
"""

import pytest

from tests.api.ledger_helpers import PASSWORD

API = "/api/v1"
IMEI = "869924030176755"


@pytest.fixture
async def store(client, create_tenant):
    owner = await create_tenant(password=PASSWORD, full_name="Dilnoza")

    async def post(path: str, body: dict) -> dict:
        response = await client.post(f"{API}{path}", headers=owner.auth, json=body)
        assert response.status_code == 201, response.text
        return response.json()["data"]

    location = await post("/locations", {"name": "Chilonzor shop"})
    walk_in = await post("/customers", {"fullName": "Aziz"})
    buyer = await post("/customers", {"fullName": "Bek"})
    phone = await post(
        "/products",
        {
            "sku": "IP15P-256",
            "name": "iPhone 15 Pro",
            "trackingType": "serial",
            "currency": "USD",
        },
    )
    return owner, {
        "location": location["id"],
        "walkIn": walk_in["id"],
        "buyer": buyer["id"],
        "phone": phone["id"],
    }


async def trade_in(client, owner, ids, *, cost="330.00", asking="420.00", som="4200000"):
    """The walk-in sale §4.5b describes: paid in som, booked in dollars."""
    opened = await client.post(
        f"{API}/receipts",
        headers=owner.auth,
        json={
            "locationId": ids["location"],
            "acquisitionSource": "trade_in",
            "customerId": ids["walkIn"],
            "lines": [{"productId": ids["phone"], "quantity": 1}],
        },
    )
    assert opened.status_code == 201, opened.text
    receipt_id = opened.json()["data"]["id"]
    scanned = await client.post(
        f"{API}/receipts/{receipt_id}/scan",
        headers=owner.auth,
        json={
            "imei": IMEI,
            "condition": "used",
            "acquisitionCost": cost,
            "askingPrice": asking,
            "cashPaid": som,
            "cashPaidCurrency": "UZS",
        },
    )
    assert scanned.status_code == 200, scanned.text
    confirmed = await client.post(
        f"{API}/receipts/{receipt_id}/confirm", headers=owner.auth, json={}
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()["data"]["number"]


async def unit_id_of(client, owner, imei=IMEI):
    found = await client.get(
        f"{API}/scan/lookup", headers=owner.auth, params={"code": imei}
    )
    assert found.status_code == 200, found.text
    return found.json()["data"]["device"]["id"]


async def cut(client, owner, unit_id, price, reason="not moving"):
    changed = await client.patch(
        f"{API}/device-units/{unit_id}/price",
        headers=owner.auth,
        json={"askingPrice": price, "reason": reason},
    )
    assert changed.status_code == 200, changed.text


async def sell_below_asking(client, owner, ids, charged="350.00", note="haggled hard"):
    created = await client.post(
        f"{API}/invoices",
        headers=owner.auth,
        json={"locationId": ids["location"], "customerId": ids["buyer"]},
    )
    invoice_id = created.json()["data"]["id"]
    scanned = await client.post(
        f"{API}/invoices/{invoice_id}/scan", headers=owner.auth, json={"code": IMEI}
    )
    line_id = scanned.json()["data"]["line"]["id"]
    overridden = await client.patch(
        f"{API}/invoices/{invoice_id}/lines/{line_id}",
        headers=owner.auth,
        json={"price": charged, "note": note},
    )
    assert overridden.status_code == 200, overridden.text
    confirmed = await client.post(
        f"{API}/invoices/{invoice_id}/confirm", headers=owner.auth
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()["data"]["number"]


async def trace(client, auth, unit_id):
    response = await client.get(f"{API}/device-units/{unit_id}/trace", headers=auth)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def a_whole_life(client, owner, ids):
    """Bought, priced, cut twice, sold below asking."""
    receipt_number = await trade_in(client, owner, ids)
    unit_id = await unit_id_of(client, owner)
    await cut(client, owner, unit_id, "390.00")
    await cut(client, owner, unit_id, "360.00")
    invoice_number = await sell_below_asking(client, owner, ids)
    return unit_id, receipt_number, invoice_number


class TestTheDemo:
    async def test_every_event_appears_once_and_in_order(self, client, store):
        owner, ids = store
        unit_id, _, _ = await a_whole_life(client, owner, ids)

        events = (await trace(client, owner.auth, unit_id))["events"]

        assert [event["kind"] for event in events] == [
            "received",
            "priced",
            "priced",
            "priced",
            "sold",
        ]
        stamps = [event["occurredAt"] for event in events]
        assert stamps == sorted(stamps)

    async def test_it_names_the_walk_in_it_was_traded_in_from(self, client, store):
        owner, ids = store
        unit_id, receipt_number, _ = await a_whole_life(client, owner, ids)

        received = (await trace(client, owner.auth, unit_id))["events"][0]

        assert received["documentNumber"] == receipt_number
        assert received["origin"]["acquisitionSource"] == "trade_in"
        assert received["origin"]["customerName"] == "Aziz"
        assert received["origin"]["supplierName"] is None
        assert received["userName"] == "Dilnoza"

    async def test_the_first_pricing_is_not_a_cut_and_the_next_two_are(
        self, client, store
    ):
        owner, ids = store
        unit_id, _, _ = await a_whole_life(client, owner, ids)

        priced = [
            event
            for event in (await trace(client, owner.auth, unit_id))["events"]
            if event["kind"] == "priced"
        ]

        assert priced[0]["oldPrice"] is None
        assert priced[0]["newPriceMinor"] == 42000
        assert [event["oldPriceMinor"] for event in priced[1:]] == [42000, 39000]
        assert [event["newPriceMinor"] for event in priced[1:]] == [39000, 36000]
        assert priced[1]["userName"] == "Dilnoza"

    async def test_the_sale_names_the_buyer_both_prices_and_the_approver(
        self, client, store
    ):
        owner, ids = store
        unit_id, _, invoice_number = await a_whole_life(client, owner, ids)

        sold = (await trace(client, owner.auth, unit_id))["events"][-1]

        assert sold["documentNumber"] == invoice_number
        assert sold["sale"]["invoiceNumber"] == invoice_number
        assert sold["sale"]["customerName"] == "Bek"
        # Sold below the price the shelf was asking at that moment.
        assert sold["sale"]["resolvedPriceMinor"] == 36000
        assert sold["sale"]["chargedPriceMinor"] == 35000
        assert sold["sale"]["priceApprovedByName"] == "Dilnoza"
        assert sold["sale"]["priceNote"] == "haggled hard"

    async def test_the_som_sits_beside_the_booked_cost_and_in_no_total(
        self, client, store
    ):
        """FR-3.4c/FR-3.4d: what physically changed hands, shown as a string
        so nothing anywhere can add it to a figure."""
        owner, ids = store
        unit_id, _, _ = await a_whole_life(client, owner, ids)

        unit = (await trace(client, owner.auth, unit_id))["unit"]

        assert unit["acquisitionCostMinor"] == 33000
        # A string beside the booked cost, never a number: there is no
        # numeric field the som could be added to anything from.
        assert unit["cashPaid"] == "4 200 000 so'm"
        assert not any(key.startswith("cashPaid") and key != "cashPaid" for key in unit)


class TestWhatTheTraceRefusesToInvent:
    async def test_changing_the_condition_adds_no_event(self, client, store):
        """FR-2.18 writes a projection and no log, so there is no date for an
        event to claim. A timeline that guesses is worse than one with a
        line missing."""
        owner, ids = store
        await trade_in(client, owner, ids)
        unit_id = await unit_id_of(client, owner)
        before = len((await trace(client, owner.auth, unit_id))["events"])

        changed = await client.patch(
            f"{API}/device-units/{unit_id}/condition",
            headers=owner.auth,
            json={"condition": "refurbished"},
        )
        assert changed.status_code == 200, changed.text

        after = (await trace(client, owner.auth, unit_id))["events"]
        assert len(after) == before


class TestACancelledSale:
    async def test_both_the_sale_and_its_reversal_are_on_the_timeline(
        self, client, store
    ):
        """§4.3 rule 3: the compensation is appended, so the trace shows the
        sale that happened and the cancellation that undid it."""
        owner, ids = store
        await trade_in(client, owner, ids)
        unit_id = await unit_id_of(client, owner)
        created = await client.post(
            f"{API}/invoices",
            headers=owner.auth,
            json={"locationId": ids["location"], "customerId": ids["buyer"]},
        )
        invoice_id = created.json()["data"]["id"]
        await client.post(
            f"{API}/invoices/{invoice_id}/scan", headers=owner.auth, json={"code": IMEI}
        )
        await client.post(f"{API}/invoices/{invoice_id}/confirm", headers=owner.auth)
        cancelled = await client.post(
            f"{API}/invoices/{invoice_id}/cancel", headers=owner.auth, json={}
        )
        assert cancelled.status_code == 200, cancelled.text

        events = (await trace(client, owner.auth, unit_id))["events"]

        assert [event["kind"] for event in events].count("sold") == 2


class TestWhatASellerSees:
    """FR-1.7: the trace is open to anyone at the store, but the cost half of
    it is omitted from the payload rather than hidden in a screen."""

    async def test_the_prices_survive_and_the_costs_do_not(self, client, store):
        owner, ids = store
        unit_id, _, _ = await a_whole_life(client, owner, ids)
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

        data = await trace(client, seller, unit_id)

        assert data["unit"]["acquisitionCost"] is None
        assert data["unit"]["acquisitionCostMinor"] is None
        assert data["unit"]["cashPaid"] is None
        priced = [event for event in data["events"] if event["kind"] == "priced"]
        assert [event["newPriceMinor"] for event in priced] == [42000, 39000, 36000]
        assert data["events"][-1]["sale"]["chargedPriceMinor"] == 35000
