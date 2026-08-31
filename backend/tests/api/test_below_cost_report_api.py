"""FR-2.19 backwards, against a real tenant database (PRD §5.9).

The weighted-average cost is rebuilt in SQL here, not replayed through
``CostPoolReader`` — so this suite is the guard that the two folds agree on a
receipt that actually moved the average across the catalog price.
"""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from application.services.cost_pools import CostPoolReader
from infrastructure.persistence.mappers import (
    FinancialTransactionMapper,
    ProductMapper,
    StockMovementMapper,
)
from infrastructure.persistence.repositories import (
    TenantSqlAppendOnlyRepository,
    TenantSqlRepository,
)
from infrastructure.persistence.tenant.models import (
    FinancialTransactionModel,
    ProductModel,
    StockMovementModel,
)
from infrastructure.persistence.tenant.queries.below_cost import SqlBelowCostQueries
from infrastructure.types import TenantSession
from tests.api.ledger_helpers import PASSWORD, tenant_url

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


async def confirm_receipt(client, owner, ids, *, quantity: int, unit_cost: str) -> dict:
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
    return confirmed.json()["data"]


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
        assert row["currency"] == "USD"

    async def test_the_confirm_response_flags_the_same_receipt(self, client, store):
        owner, ids = store
        first = await confirm_receipt(client, owner, ids, quantity=10, unit_cost="6.00")
        assert first["belowCostAlerts"] == []

        second = await confirm_receipt(
            client, owner, ids, quantity=10, unit_cost="14.00"
        )
        alerts = second["belowCostAlerts"]
        assert len(alerts) == 1
        assert alerts[0]["sku"] == "CASE-X"
        assert alerts[0]["averageUnitCostMinor"] == 1000


class TestTheTwoFoldsAgree:
    """The SQL fold and ``CostPoolReader``'s replay must land on the same
    weighted-average for a receipt that moved it across the catalog price."""

    async def test_sql_average_equals_the_replayed_pool(self, client, settings, store):
        owner, ids = store
        await confirm_receipt(client, owner, ids, quantity=10, unit_cost="6.00")
        await confirm_receipt(client, owner, ids, quantity=7, unit_cost="16.00")

        engine = create_async_engine(await tenant_url(settings, owner.tenant_id))
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as raw:
                session = TenantSession(raw)
                sql_rows, _ = await SqlBelowCostQueries(session).list_below_cost(
                    page=1, page_size=25
                )
                reader = CostPoolReader(
                    TenantSqlRepository(session, ProductModel, ProductMapper()),
                    TenantSqlAppendOnlyRepository(
                        session, StockMovementModel, StockMovementMapper()
                    ),
                    TenantSqlAppendOnlyRepository(
                        session, FinancialTransactionModel, FinancialTransactionMapper()
                    ),
                )
                assert len(sql_rows) == 1
                row = sql_rows[0]
                pool = await reader.pool_for(row.product_id, row.location_id)
                assert pool is not None
                assert pool.average_unit_cost == row.average_unit_cost
        finally:
            await engine.dispose()


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
