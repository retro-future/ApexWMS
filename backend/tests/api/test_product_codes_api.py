"""Generated SKUs, in-store barcodes and printed labels, end to end.

Runs the whole stack against a migrated Postgres, so these are what prove
the 0010 migration and the DI wiring.
"""

import pytest

from tests.api.pdf_helpers import pdf_text

PASSWORD = "hunter2000"


@pytest.fixture
async def owner(create_tenant):
    return await create_tenant(password=PASSWORD)


async def post_product(client, owner, **overrides):
    body = {"name": "iPhone 15 Pro", "trackingType": "serial"}
    return await client.post(
        "/api/v1/products", headers=owner.auth, json={**body, **overrides}
    )


class TestGeneratedSku:
    async def test_a_product_created_without_a_sku_gets_one(self, client, owner):
        first = await post_product(client, owner)
        second = await post_product(client, owner)

        assert first.status_code == 201, first.text
        assert first.json()["data"]["sku"] == "PH-000001"
        assert second.json()["data"]["sku"] == "PH-000002"

    async def test_an_accessory_gets_an_ac_number(self, client, owner):
        resp = await post_product(
            client, owner, name="Clear case", trackingType="quantity"
        )
        assert resp.json()["data"]["sku"] == "AC-000001"

    async def test_a_supplied_sku_is_still_honoured(self, client, owner):
        resp = await post_product(client, owner, sku="MY-OWN-1")
        assert resp.json()["data"]["sku"] == "MY-OWN-1"


class TestGeneratedBarcode:
    async def test_create_with_generate_barcode(self, client, owner):
        resp = await post_product(
            client,
            owner,
            name="Clear case",
            trackingType="quantity",
            generateBarcode=True,
        )
        barcode = resp.json()["data"]["barcode"]
        assert barcode is not None and barcode.startswith("20") and len(barcode) == 13

    async def test_generate_for_an_existing_accessory(self, client, owner):
        created = await post_product(
            client, owner, name="Clear case", trackingType="quantity"
        )
        product_id = created.json()["data"]["id"]

        resp = await client.post(
            f"/api/v1/products/{product_id}/barcode", headers=owner.auth
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["barcode"] is not None

        again = await client.post(
            f"/api/v1/products/{product_id}/barcode", headers=owner.auth
        )
        assert again.status_code == 409

    async def test_generate_for_a_phone_is_unprocessable(self, client, owner):
        created = await post_product(client, owner)
        product_id = created.json()["data"]["id"]

        resp = await client.post(
            f"/api/v1/products/{product_id}/barcode", headers=owner.auth
        )
        assert resp.status_code == 422


class TestLabelPdf:
    async def test_a_phone_label_encodes_the_sku(self, client, owner):
        created = await post_product(client, owner, defaultSalePrice="599.00")
        product_id = created.json()["data"]["id"]

        resp = await client.get(
            f"/api/v1/products/{product_id}/label.pdf", headers=owner.auth
        )

        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content.startswith(b"%PDF")
        page = pdf_text(resp.content)
        assert "PH-000001" in page

    async def test_an_accessory_label_encodes_the_barcode(self, client, owner):
        created = await post_product(
            client,
            owner,
            name="Clear case",
            trackingType="quantity",
            generateBarcode=True,
        )
        data = created.json()["data"]

        resp = await client.get(
            f"/api/v1/products/{data['id']}/label.pdf",
            headers=owner.auth,
            params={"layout": "sheet", "copies": 6},
        )

        assert resp.status_code == 200, resp.text
        assert resp.content.startswith(b"%PDF")
        assert data["barcode"] in pdf_text(resp.content)

    async def test_an_unknown_product_has_no_label(self, client, owner):
        resp = await client.get(
            "/api/v1/products/00000000-0000-0000-0000-0000000000ff/label.pdf",
            headers=owner.auth,
        )
        assert resp.status_code == 404


class TestScanResolvesAPhoneBySku:
    async def test_a_phone_is_found_by_its_generated_sku(self, client, owner):
        await post_product(client, owner)

        resp = await client.get(
            "/api/v1/scan/lookup", headers=owner.auth, params={"code": "PH-000001"}
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["kind"] == "product"
