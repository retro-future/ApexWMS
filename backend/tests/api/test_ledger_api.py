"""**The M3 demo, end to end against a real tenant database** (PRD §10):
a confirm writes both a stock movement and its money entry, and both
reconcile.

M4's Goods Receipt has no HTTP surface yet, so the receipt here is posted
through ``LedgerPoster`` against the same migrated Postgres the API uses —
which is what proves the 0004 migration, the foreign keys into
``employees``, and the currency joins, none of which the in-memory suites
can touch.

The handsets those postings create are then exercised over HTTP through
the unit-pricing routes (PRD §8), so the two halves meet.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from domain.enums import TransactionType
from domain.value_objects import Currency
from infrastructure.persistence.tenant.repositories import (
    SqlFinancialTransactionRepository,
    SqlStockMovementRepository,
)
from infrastructure.types import TenantSession
from tests.api.ledger_helpers import PHONE_IMEI, receive_phone, tenant_url, usd


class TestTheLedgersReconcile:
    async def test_a_receipt_writes_goods_and_money_together(self, client, settings, owner):
        """FR-10.1, against real tables: one movement, one money entry,
        one cause, one author."""
        unit_id, product_id, location_id = await receive_phone(client, settings, owner)

        engine = create_async_engine(await tenant_url(settings, owner.tenant_id))
        try:
            async with async_sessionmaker(engine)() as raw:
                session = TenantSession(raw)
                movements = await SqlStockMovementRepository(session).list_for_unit(unit_id)
                totals = await SqlFinancialTransactionRepository(session).totals_by_type()
        finally:
            await engine.dispose()

        assert [m.quantity_delta for m in movements] == [1]
        assert movements[0].user_id == UUID(owner.user_id)
        assert totals[(TransactionType.PURCHASE, Currency.USD)] == usd("-380")

    async def test_the_unit_is_readable_over_http_with_its_cost(
        self, client, settings, owner
    ):
        unit_id, _, location_id = await receive_phone(client, settings, owner)

        resp = await client.get(f"/api/v1/device-units/{unit_id}", headers=owner.auth)

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["imei"] == PHONE_IMEI
        assert data["status"] == "in_stock"
        assert data["locationId"] == str(location_id)
        assert data["acquisitionCost"] == "380.00"

    async def test_a_som_paid_trade_in_books_dollars_and_shows_som(
        self, client, settings, owner
    ):
        """§4.5b / FR-3.4c: booked at $330, paid 4 200 000 so'm — the two
        sit side by side, and only one of them is in the ledger."""
        unit_id, _, _ = await receive_phone(
            client,
            settings,
            owner,
            cost="330",
            cash_paid_minor=4_200_000,
            cash_paid_currency=Currency.UZS,
        )

        resp = await client.get(f"/api/v1/device-units/{unit_id}", headers=owner.auth)

        data = resp.json()["data"]
        assert data["acquisitionCost"] == "330.00"
        assert data["cashPaid"] == "4 200 000 so'm"

    async def test_the_som_figure_enters_no_financial_total(
        self, client, settings, owner
    ):
        """FR-3.4d — the test that exists to catch a future report quietly
        summing ``cash_paid``. The purchase is exactly −$330, and no
        figure anywhere equals or contains 4 200 000."""
        await receive_phone(
            client,
            settings,
            owner,
            cost="330",
            cash_paid_minor=4_200_000,
            cash_paid_currency=Currency.UZS,
        )

        engine = create_async_engine(await tenant_url(settings, owner.tenant_id))
        try:
            async with async_sessionmaker(engine)() as raw:
                totals = await SqlFinancialTransactionRepository(
                    TenantSession(raw)
                ).totals_by_type()
        finally:
            await engine.dispose()

        assert totals == {(TransactionType.PURCHASE, Currency.USD): usd("-330")}
        assert all(abs(amount.amount_minor) != 4_200_000 for amount in totals.values())


class TestPricingAHandsetOverHttp:
    async def test_an_unpriced_used_handset_resolves_to_no_price(
        self, client, settings, owner
    ):
        """FR-2.14 over HTTP, and §11's signature bug held at bay: the
        catalog is silent, the unit is used, and the answer is "not
        priced" rather than a number."""
        unit_id, product_id, _ = await receive_phone(client, settings, owner)
        await client.patch(
            f"/api/v1/products/{product_id}",
            headers=owner.auth,
            json={"defaultSalePrice": "900"},
        )

        resp = await client.get(f"/api/v1/device-units/{unit_id}", headers=owner.auth)

        assert resp.json()["data"]["resolvedPrice"] is None

    async def test_pricing_the_handset_makes_it_quotable(self, client, settings, owner):
        unit_id, _, _ = await receive_phone(client, settings, owner)

        priced = await client.patch(
            f"/api/v1/device-units/{unit_id}/price",
            headers=owner.auth,
            json={"askingPrice": "500"},
        )

        assert priced.status_code == 200, priced.text
        assert priced.json()["data"]["resolvedPrice"] == "500.00"

    async def test_two_cuts_leave_three_rows_in_order(self, client, settings, owner):
        """FR-2.15's stated test over HTTP, and the ``user_id`` foreign key
        into ``employees`` exercised three times."""
        unit_id, _, _ = await receive_phone(client, settings, owner)

        for price in ("420", "390", "360"):
            resp = await client.patch(
                f"/api/v1/device-units/{unit_id}/price",
                headers=owner.auth,
                json={"askingPrice": price},
            )
            assert resp.status_code == 200, resp.text

        history = await client.get(
            f"/api/v1/device-units/{unit_id}/price-history", headers=owner.auth
        )
        rows = history.json()["data"]
        assert [(r["oldPrice"], r["newPrice"]) for r in rows] == [
            (None, "420.00"),
            ("420.00", "390.00"),
            ("390.00", "360.00"),
        ]
        assert {r["userId"] for r in rows} == {owner.user_id}

    async def test_a_new_handset_follows_the_catalog_price(
        self, client, settings, owner
    ):
        """FR-2.14 step 2, and FR-2.20: cutting the catalog price moves
        what this unit quotes, with no write to ``device_units`` at all."""
        unit_id, product_id, _ = await receive_phone(
            client, settings, owner, condition="new"
        )
        await client.patch(
            f"/api/v1/products/{product_id}",
            headers=owner.auth,
            json={"defaultSalePrice": "900"},
        )

        at_first = await client.get(f"/api/v1/device-units/{unit_id}", headers=owner.auth)
        assert at_first.json()["data"]["resolvedPrice"] == "900.00"

        await client.patch(
            f"/api/v1/products/{product_id}",
            headers=owner.auth,
            json={"defaultSalePrice": "780"},
        )

        after = await client.get(f"/api/v1/device-units/{unit_id}", headers=owner.auth)
        assert after.json()["data"]["resolvedPrice"] == "780.00"
        # No row was written to the unit's own log — the price is resolved,
        # not stored twice.
        history = await client.get(
            f"/api/v1/device-units/{unit_id}/price-history", headers=owner.auth
        )
        assert history.json()["data"] == []

    async def test_flipping_a_new_unit_to_used_makes_it_unsellable(
        self, client, settings, owner
    ):
        """FR-2.18's stated test over HTTP: refused, not quoted at $900."""
        unit_id, product_id, _ = await receive_phone(
            client, settings, owner, condition="new"
        )
        await client.patch(
            f"/api/v1/products/{product_id}",
            headers=owner.auth,
            json={"defaultSalePrice": "900"},
        )

        flipped = await client.patch(
            f"/api/v1/device-units/{unit_id}/condition",
            headers=owner.auth,
            json={"condition": "used"},
        )

        assert flipped.status_code == 200, flipped.text
        assert flipped.json()["data"]["resolvedPrice"] is None

    async def test_bulk_repricing_writes_one_row_per_unit(
        self, client, settings, owner
    ):
        """FR-2.21: two handsets, one call, one shared reason."""
        first, _, _ = await receive_phone(client, settings, owner)
        second, _, _ = await receive_phone(
            client, settings, owner, imei="356938035643809"
        )

        resp = await client.post(
            "/api/v1/device-units/price",
            headers=owner.auth,
            json={
                "prices": [
                    {"deviceUnitId": str(first), "askingPrice": "400"},
                    {"deviceUnitId": str(second), "askingPrice": "450"},
                ],
                "reason": "Ramadan clearance",
            },
        )

        assert resp.status_code == 200, resp.text
        assert resp.json()["data"] == 2
        for unit_id, price in ((first, "400.00"), (second, "450.00")):
            history = await client.get(
                f"/api/v1/device-units/{unit_id}/price-history", headers=owner.auth
            )
            rows = history.json()["data"]
            assert [r["newPrice"] for r in rows] == [price]
            assert rows[0]["reason"] == "Ramadan clearance"

    async def test_an_unknown_handset_is_a_404(self, client, owner):
        resp = await client.get(
            "/api/v1/device-units/00000000-0000-0000-0000-000000000000",
            headers=owner.auth,
        )

        assert resp.status_code == 404
