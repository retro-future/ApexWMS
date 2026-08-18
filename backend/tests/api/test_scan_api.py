"""FR-7.1, FR-7.2, FR-7.4: one endpoint, and it says what it found.

The operator's scanner is a keyboard wedge that types a string and presses
Enter. It does not know whether it just read an IMEI off a handset or a
barcode off a box, so every one of these tests sends a bare string and
asserts on the ``kind`` that comes back.
"""

import pytest

from tests.api.ledger_helpers import PASSWORD

API = "/api/v1"

PHONE_IMEI = "490154203237518"
CASE_BARCODE = "4600051000057"
# Fifteen digits whose Luhn check digit is wrong — a mis-scan, and not a
# code that identifies anything in the store.
BAD_IMEI = "490154203237519"


@pytest.fixture
async def stocked(client, create_tenant):
    """A store holding one received handset and one accessory with a barcode."""
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
            "barcode": CASE_BARCODE,
            "defaultSalePrice": "50000",
        },
    )

    receipt = await post(
        "/receipts",
        {
            "locationId": location["id"],
            "acquisitionSource": "supplier",
            "supplierId": supplier["id"],
            "lines": [{"productId": phone["id"], "quantity": 1}],
        },
    )
    scanned = await client.post(
        f"{API}/receipts/{receipt['id']}/scan",
        headers=owner.auth,
        json={"imei": PHONE_IMEI, "acquisitionCost": "700.00"},
    )
    assert scanned.status_code == 200, scanned.text
    confirmed = await client.post(
        f"{API}/receipts/{receipt['id']}/confirm", headers=owner.auth, json={}
    )
    assert confirmed.status_code == 200, confirmed.text

    return owner, {"phone": phone["id"], "case": case["id"], "location": location["id"]}


async def lookup(client, headers, code: str):
    return await client.get(f"{API}/scan/lookup", headers=headers, params={"code": code})


class TestWhatTheCodeIs:
    async def test_an_imei_resolves_to_the_handset(self, client, stocked):
        owner, ids = stocked

        response = await lookup(client, owner.auth, PHONE_IMEI)

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["kind"] == "device"
        assert data["product"] is None
        assert data["device"]["imei"] == PHONE_IMEI
        assert data["device"]["productId"] == ids["phone"]
        assert data["device"]["status"] == "in_stock"
        assert data["device"]["locationId"] == ids["location"]

    async def test_scanner_separators_are_tolerated(self, client, stocked):
        """``IMEI.parse`` accepts what a label prints; the operator does not
        retype it without the spaces."""
        owner, _ = stocked

        response = await lookup(client, owner.auth, " 49015420-3237518 ")

        assert response.status_code == 200, response.text
        assert response.json()["data"]["device"]["imei"] == PHONE_IMEI

    async def test_a_barcode_resolves_to_the_catalog_row(self, client, stocked):
        owner, ids = stocked

        response = await lookup(client, owner.auth, CASE_BARCODE)

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["kind"] == "product"
        assert data["device"] is None
        assert data["product"]["id"] == ids["case"]

    async def test_a_sku_resolves_to_the_catalog_row(self, client, stocked):
        """A store printing its own labels scans the SKU, not an EAN."""
        owner, ids = stocked

        response = await lookup(client, owner.auth, "CASE-SIL-1")

        assert response.status_code == 200, response.text
        assert response.json()["data"]["product"]["id"] == ids["case"]


class TestWhatTheCodeIsNot:
    async def test_an_unknown_code_is_a_404(self, client, stocked):
        """FR-7.4: not a 500, and never an empty 200."""
        owner, _ = stocked

        response = await lookup(client, owner.auth, "NOPE-1234")

        assert response.status_code == 404, response.text
        assert response.json()["detail"]

    async def test_a_mis_scanned_imei_is_a_404_not_a_crash(self, client, stocked):
        """Fifteen digits failing the Luhn check are not an IMEI, so the
        search falls through to barcodes and SKUs and simply finds nothing."""
        owner, _ = stocked

        response = await lookup(client, owner.auth, BAD_IMEI)

        assert response.status_code == 404, response.text

    async def test_digits_that_are_not_an_imei_can_still_be_a_barcode(
        self, client, stocked
    ):
        """The barcode above is thirteen digits: proof the IMEI attempt
        falling over does not end the lookup."""
        owner, _ = stocked

        response = await lookup(client, owner.auth, CASE_BARCODE)

        assert response.status_code == 200, response.text
        assert response.json()["data"]["kind"] == "product"


class TestWhoSeesWhat:
    async def test_a_storekeeper_gets_the_price_and_not_the_cost(
        self, client, stocked
    ):
        """FR-1.7 is response shaping: the figures are absent from the
        payload, not hidden by the client. FR-7.2: the price stays, because
        that is what the counter needs."""
        owner, _ = stocked
        invite = await client.post(
            f"{API}/users/invite",
            headers=owner.auth,
            json={"email": "store@example.com", "role": "tenant.storekeeper"},
        )
        assert invite.status_code == 201, invite.text
        accepted = await client.post(
            f"{API}/auth/accept-invite",
            json={"token": invite.json()["data"]["token"], "password": "memberpass1"},
        )
        assert accepted.status_code == 201, accepted.text
        login = await client.post(
            f"{API}/auth/login",
            json={"email": "store@example.com", "password": "memberpass1"},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}

        response = await lookup(client, headers, PHONE_IMEI)

        assert response.status_code == 200, response.text
        device = response.json()["data"]["device"]
        assert device["acquisitionCost"] is None
        assert device["cashPaid"] is None
        assert device["resolvedPrice"] == "900.00"

    async def test_the_owner_sees_the_cost(self, client, stocked):
        owner, _ = stocked

        response = await lookup(client, owner.auth, PHONE_IMEI)

        assert response.json()["data"]["device"]["acquisitionCost"] == "700.00"
