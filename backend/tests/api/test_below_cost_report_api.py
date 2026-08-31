"""FR-2.19 backwards, against a real tenant database (PRD §5.9).

The weighted-average cost is rebuilt in SQL here, not replayed through
``CostPoolReader`` — so this suite is the guard that the two folds agree on a
receipt that actually moved the average across the catalog price.
"""

from uuid import uuid4

import pytest

from tests.api.ledger_helpers import PASSWORD

API = "/api/v1"


@pytest.fixture
async def store(client, create_tenant):
    """A settled Owner, one location, and one accessory priced at $10.00."""
    owner = await create_tenant(password=PASSWORD)

    location = await client.post(
        f"{API}/locations", headers=owner.auth, json={"name": "Main"}
    )
    assert location.status_code == 201, location.text
    supplier = await client.post(
        f"{API}/suppliers", headers=owner.auth, json={"name": "Accessory Source"}
    )
    assert supplier.status_code == 201, supplier.text
    product = await client.post(
        f"{API}/products",
        headers=owner.auth,
        json={
            "sku": "CASE-X",
            "name": "Silicone case",
            "trackingType": "quantity",
            "currency": "USD",
            "defaultSalePrice": "10.00",
        },
    )
    assert product.status_code == 201, product.text
    return owner, {
        "location": location.json()["data"]["id"],
        "supplier": supplier.json()["data"]["id"],
        "product": product.json()["data"]["id"],
    }


async def confirm_receipt(client, owner, ids, *, quantity: int, unit_cost: str) -> None:
    opened = await client.post(
        f"{API}/receipts",
        headers=owner.auth,
        json={
            "locationId": ids["location"],
            "supplierId": ids["supplier"],
            "lines": [
                {
                    "productId": ids["product"],
                    "quantity": quantity,
                    "unitCost": unit_cost,
                }
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


async def below_cost(client, auth, **params):
    response = await client.get(
        f"{API}/reports/below-cost", headers=auth, params=params
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestTheWorklist:
    async def test_an_accessory_below_cost_is_not_listed(self, client, store):
        owner, ids = store
        await confirm_receipt(client, owner, ids, quantity=10, unit_cost="6.00")

        body = await below_cost(client, owner.auth)

        assert body["data"] == []
        assert body["totalItems"] == 0

    async def test_it_appears_once_the_average_reaches_the_catalog_price(
        self, client, store
    ):
        owner, ids = store
        await confirm_receipt(client, owner, ids, quantity=10, unit_cost="6.00")
        await confirm_receipt(client, owner, ids, quantity=10, unit_cost="14.00")

        body = await below_cost(client, owner.auth)

        assert body["totalItems"] == 1
        row = body["data"][0]
        assert row["sku"] == "CASE-X"
        assert row["catalogPriceMinor"] == 1000
        assert row["averageUnitCostMinor"] == 1000
        assert row["quantity"] == 20


class TestWhoMayRead:
    """§2.1: a Seller cannot reprice an accessory, so the worklist that
    exists to get one repriced is not theirs (FR-1.7)."""

    async def test_a_seller_is_refused(self, client, store):
        owner, _ = store
        email = f"seller-{uuid4().hex[:6]}@example.com"
        invite = await client.post(
            f"{API}/users/invite",
            headers=owner.auth,
            json={"email": email, "role": "tenant.seller"},
        )
        assert invite.status_code == 201, invite.text
        await client.post(
            f"{API}/auth/accept-invite",
            json={"token": invite.json()["data"]["token"], "password": "sellerpass1"},
        )
        login = await client.post(
            f"{API}/auth/login", json={"email": email, "password": "sellerpass1"}
        )
        seller = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}

        refused = await client.get(f"{API}/reports/below-cost", headers=seller)

        assert refused.status_code == 403
