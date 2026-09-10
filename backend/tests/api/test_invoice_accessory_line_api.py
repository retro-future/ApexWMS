"""Adding an accessory to a draft invoice without a scanner — FR-4.2c, FR-4.2d.

Proves the wiring the application suite proves against fakes: the route,
the permission, the join that rebuilds the line, the on-hand check, and
the shared ``AccessoryLineWriter`` that the scan path also uses.
"""

from uuid import uuid4

API = "/api/v1"


async def a_store(client, owner) -> dict:
    listed = await client.get(f"{API}/locations", headers=owner.auth)
    assert listed.status_code == 200, listed.text
    supplier = await client.post(
        f"{API}/suppliers", headers=owner.auth, json={"name": "Case Source"}
    )
    assert supplier.status_code == 201, supplier.text
    return {
        "location": listed.json()["data"][0]["id"],
        "supplier": supplier.json()["data"]["id"],
    }


async def an_accessory(client, owner, *, price: str | None = "50000") -> str:
    body = {
        "sku": f"CASE-{uuid4().hex[:6]}",
        "name": "Clear case",
        "trackingType": "quantity",
    }
    if price is not None:
        body["defaultSalePrice"] = price
    created = await client.post(f"{API}/products", headers=owner.auth, json=body)
    assert created.status_code == 201, created.text
    return created.json()["data"]["id"]


async def receive(client, owner, ids, product_id, quantity: int) -> None:
    opened = await client.post(
        f"{API}/receipts",
        headers=owner.auth,
        json={
            "locationId": ids["location"],
            "supplierId": ids["supplier"],
            "lines": [
                {"productId": product_id, "quantity": quantity, "unitCost": "10000"}
            ],
        },
    )
    assert opened.status_code == 201, opened.text
    confirmed = await client.post(
        f"{API}/receipts/{opened.json()['data']['id']}/confirm",
        headers=owner.auth,
        json={},
    )
    assert confirmed.status_code == 200, confirmed.text


async def open_invoice(client, owner, location_id) -> str:
    created = await client.post(
        f"{API}/invoices", headers=owner.auth, json={"locationId": location_id}
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]["id"]


class TestAddingAnAccessoryByCatalogPick:
    async def test_a_quantity_and_a_price_land_as_one_line(self, client, owner):
        ids = await a_store(client, owner)
        product_id = await an_accessory(client, owner)
        await receive(client, owner, ids, product_id, 10)
        invoice_id = await open_invoice(client, owner, ids["location"])

        added = await client.post(
            f"{API}/invoices/{invoice_id}/lines",
            headers=owner.auth,
            json={"productId": product_id, "quantity": 3},
        )

        assert added.status_code == 201, added.text
        data = added.json()["data"]
        assert data["line"]["quantity"] == 3
        assert data["resolvedPrice"]["minor"] == 50000
        assert data["lineCount"] == 1

    async def test_the_same_product_again_merges_into_the_line(self, client, owner):
        ids = await a_store(client, owner)
        product_id = await an_accessory(client, owner)
        await receive(client, owner, ids, product_id, 10)
        invoice_id = await open_invoice(client, owner, ids["location"])
        await client.post(
            f"{API}/invoices/{invoice_id}/lines",
            headers=owner.auth,
            json={"productId": product_id, "quantity": 2},
        )

        again = await client.post(
            f"{API}/invoices/{invoice_id}/lines",
            headers=owner.auth,
            json={"productId": product_id, "quantity": 1},
        )

        assert again.status_code == 201, again.text
        assert again.json()["data"]["line"]["quantity"] == 3
        read = await client.get(f"{API}/invoices/{invoice_id}", headers=owner.auth)
        assert len(read.json()["data"]["lines"]) == 1

    async def test_selling_more_than_is_in_stock_is_refused(self, client, owner):
        ids = await a_store(client, owner)
        product_id = await an_accessory(client, owner)
        await receive(client, owner, ids, product_id, 2)
        invoice_id = await open_invoice(client, owner, ids["location"])

        refused = await client.post(
            f"{API}/invoices/{invoice_id}/lines",
            headers=owner.auth,
            json={"productId": product_id, "quantity": 3},
        )

        assert refused.status_code == 409, refused.text
        read = await client.get(f"{API}/invoices/{invoice_id}", headers=owner.auth)
        assert read.json()["data"]["lines"] == []

    async def test_an_accessory_with_no_catalog_price_is_refused(self, client, owner):
        ids = await a_store(client, owner)
        product_id = await an_accessory(client, owner, price=None)
        await receive(client, owner, ids, product_id, 10)
        invoice_id = await open_invoice(client, owner, ids["location"])

        refused = await client.post(
            f"{API}/invoices/{invoice_id}/lines",
            headers=owner.auth,
            json={"productId": product_id},
        )

        assert refused.status_code == 409, refused.text

    async def test_a_phone_product_is_refused(self, client, owner):
        ids = await a_store(client, owner)
        phone = await client.post(
            f"{API}/products",
            headers=owner.auth,
            json={
                "sku": f"IP15-{uuid4().hex[:6]}",
                "name": "iPhone 15",
                "trackingType": "serial",
            },
        )
        assert phone.status_code == 201, phone.text
        invoice_id = await open_invoice(client, owner, ids["location"])

        refused = await client.post(
            f"{API}/invoices/{invoice_id}/lines",
            headers=owner.auth,
            json={"productId": phone.json()["data"]["id"]},
        )

        assert refused.status_code == 409, refused.text
        assert "IMEI" in refused.json()["detail"]

    async def test_an_unknown_product_is_a_404(self, client, owner):
        ids = await a_store(client, owner)
        invoice_id = await open_invoice(client, owner, ids["location"])

        missing = await client.post(
            f"{API}/invoices/{invoice_id}/lines",
            headers=owner.auth,
            json={"productId": str(uuid4())},
        )

        assert missing.status_code == 404, missing.text
