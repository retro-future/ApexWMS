"""The device-inventory list against real tables — FR-9.1 at the unit level.

The application suite covers the payload shaping. This one proves the SQL: the
joins that name the product and location, the status filter, and the derived
``customer_returned`` case, which is a ``CUSTOMER_RETURN`` movement rather than
a status.
"""

from tests.api.ledger_helpers import PHONE_IMEI, receive_phone

SECOND_IMEI = "356938035643809"
API = "/api/v1"


async def inventory(client, auth, **params):
    response = await client.get(
        f"{API}/reports/device-units", headers=auth, params=params
    )
    assert response.status_code == 200, response.text
    return response.json()


async def reprice(client, owner, unit_id, price):
    changed = await client.patch(
        f"{API}/device-units/{unit_id}/price",
        headers=owner.auth,
        json={"askingPrice": price, "reason": "priced for sale"},
    )
    assert changed.status_code == 200, changed.text


async def sell(client, owner, location_id, code):
    created = await client.post(
        f"{API}/invoices", headers=owner.auth, json={"locationId": str(location_id)}
    )
    invoice_id = created.json()["data"]["id"]
    scanned = await client.post(
        f"{API}/invoices/{invoice_id}/scan", headers=owner.auth, json={"code": code}
    )
    assert scanned.status_code == 200, scanned.text
    confirmed = await client.post(
        f"{API}/invoices/{invoice_id}/confirm", headers=owner.auth
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()["data"]["id"]


async def customer_return(client, owner, location_id, invoice_id, code):
    created = await client.post(
        f"{API}/customer-returns",
        headers=owner.auth,
        json={
            "salesInvoiceId": str(invoice_id),
            "locationId": str(location_id),
            "reason": "defective",
        },
    )
    assert created.status_code == 201, created.text
    document_id = created.json()["data"]["id"]
    scanned = await client.post(
        f"{API}/customer-returns/{document_id}/scan",
        headers=owner.auth,
        json={"code": code},
    )
    assert scanned.status_code == 200, scanned.text
    confirmed = await client.post(
        f"{API}/customer-returns/{document_id}/confirm", headers=owner.auth, json={}
    )
    assert confirmed.status_code == 200, confirmed.text


class TestTheList:
    async def test_every_handset_shows_with_its_product_and_location(
        self, client, settings, owner
    ):
        unit_id, product_id, location_id = await receive_phone(
            client, settings, owner, condition="used"
        )
        await reprice(client, owner, unit_id, "500")

        body = await inventory(client, owner.auth)

        assert body["totalItems"] == 1
        row = body["data"][0]
        assert row["deviceUnitId"] == str(unit_id)
        assert row["imei"] == PHONE_IMEI
        assert row["productId"] == str(product_id)
        assert row["productName"] == "iPhone 15 Pro"
        assert row["locationId"] == str(location_id)
        assert row["status"] == "in_stock"
        assert row["wasCustomerReturned"] is False
        assert row["resolvedPriceMinor"] == 50000
        assert row["acquisitionCostMinor"] == 38000
        assert row["impliedMarginMinor"] == 12000

    async def test_a_seller_is_refused(self, client, settings, owner):
        """§2.1: Reporting.View is Manager and Owner only, like every report."""
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

        refused = await client.get(f"{API}/reports/device-units", headers=seller)
        assert refused.status_code == 403


class TestTheStatusFilter:
    async def test_sold_lists_only_the_sold_unit(self, client, settings, owner):
        sold_id, _, location_id = await receive_phone(
            client, settings, owner, condition="used"
        )
        await reprice(client, owner, sold_id, "500")
        kept_id, _, _ = await receive_phone(
            client, settings, owner, condition="used", imei=SECOND_IMEI
        )
        await reprice(client, owner, kept_id, "500")
        await sell(client, owner, location_id, PHONE_IMEI)

        body = await inventory(client, owner.auth, status="sold")

        assert [row["deviceUnitId"] for row in body["data"]] == [str(sold_id)]

    async def test_customer_returned_finds_a_unit_back_in_stock(
        self, client, settings, owner
    ):
        unit_id, _, location_id = await receive_phone(
            client, settings, owner, condition="used"
        )
        await reprice(client, owner, unit_id, "500")
        invoice_id = await sell(client, owner, location_id, PHONE_IMEI)
        await customer_return(client, owner, location_id, invoice_id, PHONE_IMEI)

        returned = await inventory(client, owner.auth, status="customer_returned")
        assert [row["deviceUnitId"] for row in returned["data"]] == [str(unit_id)]
        assert returned["data"][0]["status"] == "in_stock"
        assert returned["data"][0]["wasCustomerReturned"] is True

        assert (await inventory(client, owner.auth, status="sold"))["totalItems"] == 0
        in_stock = await inventory(client, owner.auth, status="in_stock")
        assert [row["deviceUnitId"] for row in in_stock["data"]] == [str(unit_id)]


class TestTheProductFilter:
    async def test_search_matches_the_model_name(self, client, settings, owner):
        await receive_phone(client, settings, owner, condition="used")

        assert (await inventory(client, owner.auth, productSearch="iphone"))[
            "totalItems"
        ] == 1
        assert (await inventory(client, owner.auth, productSearch="galaxy"))[
            "totalItems"
        ] == 0
