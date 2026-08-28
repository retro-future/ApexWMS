"""The M2 demo, end to end against a real tenant database: build a catalog.

These run the whole stack — router, permission check, handler, SQLAlchemy
repository, migrated Postgres — so they are what proves the 0002 migration
and the DI wiring, not just the use-case logic.
"""

from uuid import uuid4

import pytest

PASSWORD = "hunter2000"
EAN13 = "4006381333931"
OTHER_EAN13 = "5901234123457"


@pytest.fixture
async def owner(create_tenant):
    return await create_tenant(password=PASSWORD)


async def post_product(client, owner, **overrides):
    body = {"sku": "IP15P-256", "name": "iPhone 15 Pro", "trackingType": "serial"}
    return await client.post(
        "/api/v1/products", headers=owner.auth, json={**body, **overrides}
    )


class TestProducts:
    async def test_a_phone_defaults_to_usd_and_an_accessory_to_som(self, client, owner):
        """FR-2.6 over HTTP: neither request named a currency."""
        phone = await post_product(client, owner)
        case = await post_product(
            client, owner, sku="CASE-CLEAR", name="Clear case", trackingType="quantity"
        )

        assert phone.status_code == 201, phone.text
        assert phone.json()["data"]["currency"] == "USD"
        assert case.json()["data"]["currency"] == "UZS"

    async def test_a_price_survives_a_round_trip_exactly(self, client, owner):
        """FR-2.8/2.9: no float ever touches the amount. $600.00 is stored
        as 60 000 cents and read back as the string "600.00"."""
        created = await post_product(client, owner, defaultSalePrice="600.00")
        product_id = created.json()["data"]["id"]

        fetched = await client.get(f"/api/v1/products/{product_id}", headers=owner.auth)

        data = fetched.json()["data"]
        assert data["defaultSalePriceMinor"] == 60000
        assert data["defaultSalePrice"] == "600.00"

    async def test_som_and_dollars_of_the_same_magnitude_store_differently(
        self, client, owner
    ):
        """The exponent trap (PRD §4.5), asserted where it would corrupt
        real data: 1000 UZS is 1000, 1000 USD is 100000."""
        phone = await post_product(client, owner, defaultSalePrice="1000")
        case = await post_product(
            client,
            owner,
            sku="CASE-CLEAR",
            name="Clear case",
            trackingType="quantity",
            defaultSalePrice="1000",
        )

        assert phone.json()["data"]["defaultSalePriceMinor"] == 100_000
        assert case.json()["data"]["defaultSalePriceMinor"] == 1_000

    async def test_a_duplicate_sku_is_a_conflict(self, client, owner):
        await post_product(client, owner)

        again = await post_product(client, owner, name="A different phone")

        assert again.status_code == 409

    async def test_a_barcode_on_a_serial_product_is_unprocessable(self, client, owner):
        """FR-2.3, and the 422 comes from the entity's own invariant."""
        resp = await post_product(client, owner, barcode=EAN13)

        assert resp.status_code == 422

    async def test_a_duplicate_barcode_is_a_conflict(self, client, owner):
        await post_product(
            client, owner, sku="CASE-A", trackingType="quantity", barcode=EAN13
        )

        again = await post_product(
            client, owner, sku="CASE-B", trackingType="quantity", barcode=EAN13
        )

        assert again.status_code == 409

    async def test_the_unique_barcode_index_tolerates_many_unpriced_phones(
        self, client, owner
    ):
        """Postgres treats NULLs as distinct, which is what lets every
        SERIAL product carry no barcode under a unique index."""
        first = await post_product(client, owner, sku="PHONE-A")
        second = await post_product(client, owner, sku="PHONE-B")

        assert (first.status_code, second.status_code) == (201, 201)

    async def test_deactivating_keeps_the_row_and_it_stays_listable(self, client, owner):
        """FR-2.4: new movements are prevented, all history preserved."""
        created = await post_product(client, owner)
        product_id = created.json()["data"]["id"]

        patched = await client.patch(
            f"/api/v1/products/{product_id}", headers=owner.auth, json={"isActive": False}
        )

        assert patched.status_code == 200
        assert patched.json()["data"]["isActive"] is False
        retired = await client.get(
            "/api/v1/products", headers=owner.auth, params={"isActive": False}
        )
        assert [p["sku"] for p in retired.json()["data"]] == ["IP15P-256"]

    async def test_there_is_no_way_to_change_tracking_type_or_currency(
        self, client, owner
    ):
        """FR-2.1. The fields are absent from the command, so pydantic
        ignores them rather than the handler having to refuse them."""
        created = await post_product(client, owner)
        product_id = created.json()["data"]["id"]

        patched = await client.patch(
            f"/api/v1/products/{product_id}",
            headers=owner.auth,
            json={"trackingType": "quantity", "currency": "UZS"},
        )

        data = patched.json()["data"]
        assert data["trackingType"] == "serial"
        assert data["currency"] == "USD"

    async def test_delete_is_not_offered(self, client, owner):
        created = await post_product(client, owner)
        product_id = created.json()["data"]["id"]

        resp = await client.delete(f"/api/v1/products/{product_id}", headers=owner.auth)

        assert resp.status_code == 405

    async def test_an_unknown_product_is_not_found(self, client, owner):
        resp = await client.get(
            "/api/v1/products/00000000-0000-0000-0000-0000000000ff", headers=owner.auth
        )

        assert resp.status_code == 404

    async def test_the_list_pages_and_reports_the_unpaged_total(self, client, owner):
        for n in range(7):
            await post_product(client, owner, sku=f"SKU-{n}", name=f"Product {n}")

        page = await client.get(
            "/api/v1/products", headers=owner.auth, params={"page": 2, "pageSize": 3}
        )

        body = page.json()
        assert [p["sku"] for p in body["data"]] == ["SKU-3", "SKU-4", "SKU-5"]
        assert (body["totalItems"], body["pagesCount"], body["pageIndex"]) == (7, 3, 2)

    async def test_the_default_page_size_is_fifty(self, client, owner):
        """PRD §9: list endpoints paginate by default at 50."""
        await post_product(client, owner)

        page = await client.get("/api/v1/products", headers=owner.auth)

        assert page.json()["pageSize"] == 50

    async def test_search_matches_sku_name_and_brand(self, client, owner):
        await post_product(client, owner, brand="Apple")
        await post_product(client, owner, sku="SG-S24", name="Galaxy S24", brand="Samsung")

        found = await client.get(
            "/api/v1/products", headers=owner.auth, params={"search": "samsung"}
        )

        assert [p["sku"] for p in found.json()["data"]] == ["SG-S24"]


class TestCatalogPriceHistory:
    """FR-2.19 / FR-9.2b against the real 0003 migration — the log's
    ``user_id`` is a genuine foreign key into ``employees``, so these are
    what prove the "``Employee.id`` *is* the master ``User.id``" contract
    (PRD §3.1) holds at the database level and not just in prose."""

    async def test_the_owner_who_set_a_price_is_recorded_as_its_author(
        self, client, owner
    ):
        created = await post_product(client, owner, defaultSalePrice="900")
        product_id = created.json()["data"]["id"]

        history = await client.get(
            f"/api/v1/products/{product_id}/price-history", headers=owner.auth
        )

        rows = history.json()["data"]
        assert len(rows) == 1
        assert rows[0]["userId"] == owner.user_id
        assert rows[0]["oldPrice"] is None

    async def test_two_cuts_leave_three_rows_and_the_product_shows_the_last(
        self, client, owner
    ):
        """FR-2.19's stated test, over HTTP: $900 → $850 → $780."""
        created = await post_product(client, owner, defaultSalePrice="900")
        product_id = created.json()["data"]["id"]

        for price in ("850", "780"):
            patched = await client.patch(
                f"/api/v1/products/{product_id}",
                headers=owner.auth,
                json={"defaultSalePrice": price},
            )
            assert patched.status_code == 200, patched.text

        product = await client.get(f"/api/v1/products/{product_id}", headers=owner.auth)
        assert product.json()["data"]["defaultSalePrice"] == "780.00"

        history = await client.get(
            f"/api/v1/products/{product_id}/price-history", headers=owner.auth
        )
        rows = history.json()["data"]
        assert [(r["oldPrice"], r["newPrice"]) for r in rows] == [
            (None, "900.00"),
            ("900.00", "850.00"),
            ("850.00", "780.00"),
        ]

    async def test_a_reason_survives_the_round_trip(self, client, owner):
        created = await post_product(client, owner, defaultSalePrice="900")
        product_id = created.json()["data"]["id"]

        await client.patch(
            f"/api/v1/products/{product_id}",
            headers=owner.auth,
            json={"defaultSalePrice": "780", "priceReason": "iPhone 16 shipped"},
        )

        history = await client.get(
            f"/api/v1/products/{product_id}/price-history", headers=owner.auth
        )
        assert history.json()["data"][-1]["reason"] == "iPhone 16 shipped"

    async def test_a_som_priced_accessory_logs_whole_som(self, client, owner):
        """UZS is exponent 0 (PRD §4.5): 50 000 so'm is stored as 50000,
        not 5 000 000. The log inherits the product's currency rather than
        carrying one, so this is the check that the join recovers it."""
        created = await post_product(
            client,
            owner,
            sku="CASE-CLEAR",
            name="Clear case",
            trackingType="quantity",
            defaultSalePrice="50000",
        )
        product_id = created.json()["data"]["id"]

        history = await client.get(
            f"/api/v1/products/{product_id}/price-history", headers=owner.auth
        )

        row = history.json()["data"][0]
        assert (row["currency"], row["newPriceMinor"], row["newPrice"]) == (
            "UZS",
            50000,
            "50000",
        )

    async def test_a_price_cannot_be_cleared_once_set(self, client, owner):
        """The projection would otherwise contradict the log it is derived
        from — there is no row meaning "no longer priced" (FR-2.19)."""
        created = await post_product(client, owner, defaultSalePrice="900")
        product_id = created.json()["data"]["id"]

        resp = await client.patch(
            f"/api/v1/products/{product_id}",
            headers=owner.auth,
            json={"defaultSalePrice": None},
        )

        assert resp.status_code == 422, resp.text
        product = await client.get(f"/api/v1/products/{product_id}", headers=owner.auth)
        assert product.json()["data"]["defaultSalePrice"] == "900.00"

    async def test_an_unknown_product_has_no_history_to_read(self, client, owner):
        resp = await client.get(
            "/api/v1/products/00000000-0000-0000-0000-000000000000/price-history",
            headers=owner.auth,
        )

        assert resp.status_code == 404


class TestReferenceData:
    async def test_provisioning_already_seeded_a_location(self, client, owner):
        """PRD §3.4 — a new store can receive goods before anyone opens the
        settings screen. The 0002 migration backfilled its created_at."""
        resp = await client.get("/api/v1/locations", headers=owner.auth)

        assert [loc["name"] for loc in resp.json()["data"]] == ["Main Store"]

    async def test_adding_a_warehouse(self, client, owner):
        created = await client.post(
            "/api/v1/locations", headers=owner.auth, json={"name": "Warehouse"}
        )

        assert created.status_code == 201
        listed = await client.get("/api/v1/locations", headers=owner.auth)
        assert [loc["name"] for loc in listed.json()["data"]] == ["Main Store", "Warehouse"]

    async def test_a_duplicate_location_name_is_a_conflict(self, client, owner):
        resp = await client.post(
            "/api/v1/locations", headers=owner.auth, json={"name": "Main Store"}
        )

        assert resp.status_code == 409

    async def test_creating_and_reading_a_supplier(self, client, owner):
        created = await client.post(
            "/api/v1/suppliers",
            headers=owner.auth,
            json={
                "name": "Tashkent Mobile Distribution",
                "contactName": "Aziz",
                "phone": "+998901234567",
                "email": "aziz@tmd.uz",
            },
        )
        supplier_id = created.json()["data"]["id"]

        fetched = await client.get(f"/api/v1/suppliers/{supplier_id}", headers=owner.auth)

        assert created.status_code == 201, created.text
        assert fetched.json()["data"]["contactName"] == "Aziz"

    async def test_a_duplicate_supplier_name_is_a_conflict(self, client, owner):
        await client.post("/api/v1/suppliers", headers=owner.auth, json={"name": "TMD"})

        again = await client.post(
            "/api/v1/suppliers", headers=owner.auth, json={"name": "TMD"}
        )

        assert again.status_code == 409

    # The cases below ran against in-memory fakes until suppliers moved to
    # the specification-based repository. A specification carries SQLAlchemy
    # predicates, so there is nothing left for a fake to evaluate — they run
    # against the real database now.

    async def test_a_supplier_carries_no_currency(self, client, owner):
        """Currency belongs to the product (PRD §4.5 rule 3) — one supplier
        can invoice in dollars and in som on the same order."""
        created = await client.post(
            "/api/v1/suppliers", headers=owner.auth, json={"name": "TMD"}
        )

        assert "currency" not in created.json()["data"]

    async def test_an_omitted_contact_field_is_left_alone(self, client, owner):
        created = await client.post(
            "/api/v1/suppliers",
            headers=owner.auth,
            json={"name": "TMD", "phone": "+998901234567"},
        )
        supplier_id = created.json()["data"]["id"]

        patched = await client.patch(
            f"/api/v1/suppliers/{supplier_id}",
            headers=owner.auth,
            json={"contactName": "Aziz"},
        )

        assert patched.json()["data"]["phone"] == "+998901234567"
        assert patched.json()["data"]["contactName"] == "Aziz"

    async def test_an_explicit_null_clears_a_contact_field(self, client, owner):
        created = await client.post(
            "/api/v1/suppliers",
            headers=owner.auth,
            json={"name": "TMD", "phone": "+998901234567"},
        )
        supplier_id = created.json()["data"]["id"]

        patched = await client.patch(
            f"/api/v1/suppliers/{supplier_id}",
            headers=owner.auth,
            json={"phone": None},
        )

        assert patched.json()["data"]["phone"] is None

    async def test_renaming_onto_another_suppliers_name_is_a_conflict(self, client, owner):
        await client.post("/api/v1/suppliers", headers=owner.auth, json={"name": "TMD"})
        other = await client.post(
            "/api/v1/suppliers", headers=owner.auth, json={"name": "Samarkand Parts"}
        )

        renamed = await client.patch(
            f"/api/v1/suppliers/{other.json()['data']['id']}",
            headers=owner.auth,
            json={"name": "TMD"},
        )

        assert renamed.status_code == 409

    async def test_renaming_a_supplier_to_its_own_name_is_allowed(self, client, owner):
        """The uniqueness probe excludes the supplier being renamed — without
        that, saving a form that did not touch the name would 409."""
        created = await client.post(
            "/api/v1/suppliers", headers=owner.auth, json={"name": "TMD"}
        )

        renamed = await client.patch(
            f"/api/v1/suppliers/{created.json()['data']['id']}",
            headers=owner.auth,
            json={"name": "TMD", "contactName": "Aziz"},
        )

        assert renamed.status_code == 200, renamed.text

    async def test_reading_an_unknown_supplier_is_a_404(self, client, owner):
        resp = await client.get(
            f"/api/v1/suppliers/{uuid4()}", headers=owner.auth
        )

        assert resp.status_code == 404

    async def test_the_supplier_list_searches_name_and_phone(self, client, owner):
        await client.post(
            "/api/v1/suppliers",
            headers=owner.auth,
            json={"name": "TMD", "phone": "+998901234567"},
        )
        await client.post(
            "/api/v1/suppliers", headers=owner.auth, json={"name": "Samarkand Parts"}
        )

        by_name = await client.get(
            "/api/v1/suppliers", headers=owner.auth, params={"search": "samarkand"}
        )
        by_phone = await client.get(
            "/api/v1/suppliers", headers=owner.auth, params={"search": "9012345"}
        )

        assert [s["name"] for s in by_name.json()["data"]] == ["Samarkand Parts"]
        assert [s["name"] for s in by_phone.json()["data"]] == ["TMD"]

    async def test_the_supplier_list_pages_and_reports_the_unpaged_total(self, client, owner):
        """count() and find() take the same specification object, so a filter
        can never be applied to the rows and forgotten on the total."""
        for name in ("Alpha", "Beta", "Gamma"):
            await client.post("/api/v1/suppliers", headers=owner.auth, json={"name": name})

        page = await client.get(
            "/api/v1/suppliers",
            headers=owner.auth,
            params={"page": 1, "pageSize": 2, "search": "a"},
        )

        assert len(page.json()["data"]) == 2
        assert page.json()["totalItems"] == 3

    async def test_two_customers_may_share_a_name(self, client, owner):
        first = await client.post(
            "/api/v1/customers", headers=owner.auth, json={"fullName": "Aziz Karimov"}
        )
        second = await client.post(
            "/api/v1/customers", headers=owner.auth, json={"fullName": "Aziz Karimov"}
        )

        assert (first.status_code, second.status_code) == (201, 201)
        assert first.json()["data"]["id"] != second.json()["data"]["id"]

    async def test_a_customer_can_be_found_by_phone(self, client, owner):
        await client.post(
            "/api/v1/customers",
            headers=owner.auth,
            json={"fullName": "Aziz Karimov", "phone": "+998901111111"},
        )
        await client.post(
            "/api/v1/customers",
            headers=owner.auth,
            json={"fullName": "Nodira Yusupova", "phone": "+998902222222"},
        )

        found = await client.get(
            "/api/v1/customers", headers=owner.auth, params={"search": "902222222"}
        )

        assert [c["fullName"] for c in found.json()["data"]] == ["Nodira Yusupova"]
