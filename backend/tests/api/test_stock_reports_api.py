"""M8's stock-side reports against real tables — PRD §5.9.

What these pin down is the needs-pricing filter (FR-9.6), because it states
FR-2.14 a second time, in SQL. The agreement test below is the guard on
that: every row the worklist returns must be a unit ``PriceResolver``
really does refuse, and every unit it refuses must be on the worklist.
"""

from tests.api.ledger_helpers import PHONE_IMEI, receive_phone

SECOND_IMEI = "356938035643809"


async def needs_pricing(client, auth, **params):
    response = await client.get(
        "/api/v1/reports/needs-pricing", headers=auth, params=params
    )
    assert response.status_code == 200, response.text
    return response.json()


async def resolved_price(client, owner, unit_id):
    response = await client.get(f"/api/v1/device-units/{unit_id}", headers=owner.auth)
    assert response.status_code == 200, response.text
    return response.json()["data"]["resolvedPrice"]


async def price_the_catalog_row(client, owner, product_id, price):
    updated = await client.patch(
        f"/api/v1/products/{product_id}",
        headers=owner.auth,
        json={"defaultSalePrice": price},
    )
    assert updated.status_code == 200, updated.text


class TestWhatLandsOnTheWorklist:
    async def test_a_used_handset_nobody_priced_needs_its_own_price(
        self, client, settings, owner
    ):
        unit_id, _, _ = await receive_phone(client, settings, owner, condition="used")

        body = await needs_pricing(client, owner.auth)

        assert body["totalItems"] == 1
        row = body["data"][0]
        assert row["deviceUnitId"] == str(unit_id)
        assert row["imei"] == PHONE_IMEI
        assert row["condition"] == "used"
        assert row["reason"] == "used_no_price"

    async def test_a_new_handset_waits_on_a_catalog_price_instead(
        self, client, settings, owner
    ):
        await receive_phone(client, settings, owner, condition="new")

        body = await needs_pricing(client, owner.auth)

        assert body["totalItems"] == 1
        assert body["data"][0]["reason"] == "no_catalog_price"

    async def test_the_row_names_the_model_and_where_it_is_sitting(
        self, client, settings, owner
    ):
        _, product_id, location_id = await receive_phone(
            client, settings, owner, condition="used"
        )

        row = (await needs_pricing(client, owner.auth))["data"][0]

        assert row["productId"] == str(product_id)
        assert row["productName"] == "iPhone 15 Pro"
        assert row["locationId"] == str(location_id)
        assert row["locationName"]
        assert row["daysUnpriced"] == 0

    async def test_it_carries_no_cost_at_all(self, client, settings, owner):
        """The list exists so a handset gets a price, not so anyone reads a
        margin off it — even the Owner, who may see costs elsewhere."""
        await receive_phone(client, settings, owner, condition="used")

        row = (await needs_pricing(client, owner.auth))["data"][0]

        assert "acquisitionCost" not in row
        assert "cashPaid" not in row


class TestWhatDoesNot:
    async def test_a_priced_handset_drops_off(self, client, settings, owner):
        unit_id, _, _ = await receive_phone(client, settings, owner, condition="used")

        await client.patch(
            f"/api/v1/device-units/{unit_id}/price",
            headers=owner.auth,
            json={"askingPrice": "500", "reason": "priced for sale"},
        )

        assert (await needs_pricing(client, owner.auth))["totalItems"] == 0

    async def test_a_new_handset_under_a_priced_catalog_row_never_appears(
        self, client, settings, owner
    ):
        """FR-2.14 step 2: a ``NEW`` unit inherits the catalog price, so it
        is sellable without one of its own."""
        _, product_id, _ = await receive_phone(
            client, settings, owner, condition="new"
        )

        await price_the_catalog_row(client, owner, product_id, "900")

        assert (await needs_pricing(client, owner.auth))["totalItems"] == 0

    async def test_a_used_handset_under_a_priced_catalog_row_still_appears(
        self, client, settings, owner
    ):
        """The signature bug this whole rule exists to prevent: a $900
        catalog row must not make a used handset look priced."""
        _, product_id, _ = await receive_phone(
            client, settings, owner, condition="used"
        )

        await price_the_catalog_row(client, owner, product_id, "900")

        assert (await needs_pricing(client, owner.auth))["totalItems"] == 1


class TestTheWorklistAgreesWithThePriceResolver:
    """The filter is FR-2.14 stated in SQL, so it can drift from the domain
    service that states it in Python. Both are asked about the same units."""

    async def test_every_listed_unit_really_resolves_to_no_price(
        self, client, settings, owner
    ):
        used, _, _ = await receive_phone(client, settings, owner, condition="used")
        new, _, _ = await receive_phone(
            client, settings, owner, condition="new", imei=SECOND_IMEI
        )

        body = await needs_pricing(client, owner.auth)

        listed = {row["deviceUnitId"] for row in body["data"]}
        assert listed == {str(used), str(new)}
        for unit_id in (used, new):
            assert await resolved_price(client, owner, unit_id) is None

    async def test_a_unit_the_resolver_prices_is_not_listed(
        self, client, settings, owner
    ):
        unit_id, product_id, _ = await receive_phone(
            client, settings, owner, condition="new"
        )
        await price_the_catalog_row(client, owner, product_id, "900")

        assert await resolved_price(client, owner, unit_id) is not None
        assert (await needs_pricing(client, owner.auth))["totalItems"] == 0


class TestFiltering:
    async def test_another_location_matches_nothing(self, client, settings, owner):
        await receive_phone(client, settings, owner, condition="used")

        body = await needs_pricing(
            client, owner.auth, locationId="00000000-0000-0000-0000-000000000001"
        )

        assert body["totalItems"] == 0

    async def test_its_own_location_matches(self, client, settings, owner):
        _, _, location_id = await receive_phone(
            client, settings, owner, condition="used"
        )

        body = await needs_pricing(client, owner.auth, locationId=str(location_id))

        assert body["totalItems"] == 1


class TestWhoMayRead:
    """§2.1: a Seller cannot price a handset, so the worklist that exists to
    get one priced is not theirs."""

    async def test_a_seller_is_refused(self, client, settings, owner):
        invite = await client.post(
            "/api/v1/users/invite",
            headers=owner.auth,
            json={"email": "seller@example.com", "role": "tenant.seller"},
        )
        await client.post(
            "/api/v1/auth/accept-invite",
            json={"token": invite.json()["data"]["token"], "password": "sellerpass1"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "seller@example.com", "password": "sellerpass1"},
        )
        seller = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}

        refused = await client.get("/api/v1/reports/needs-pricing", headers=seller)

        assert refused.status_code == 403


async def ageing(client, auth, **params):
    response = await client.get("/api/v1/reports/ageing", headers=auth, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def reprice(client, owner, unit_id, price):
    changed = await client.patch(
        f"/api/v1/device-units/{unit_id}/price",
        headers=owner.auth,
        json={"askingPrice": price, "reason": "not moving"},
    )
    assert changed.status_code == 200, changed.text


class TestAgeing:
    async def test_a_handset_in_stock_reports_its_cost_price_and_margin(
        self, client, settings, owner
    ):
        unit_id, _, _ = await receive_phone(client, settings, owner, cost="380")
        await reprice(client, owner, unit_id, "500")

        row = (await ageing(client, owner.auth, days=0))["data"][0]

        assert row["imei"] == PHONE_IMEI
        assert row["acquisitionCostMinor"] == 38000
        assert row["askingPriceMinor"] == 50000
        assert row["impliedMarginMinor"] == 12000
        assert row["daysInStock"] == 0

    async def test_an_unpriced_handset_implies_no_margin(
        self, client, settings, owner
    ):
        """Zero would read as a margin. There isn't one."""
        await receive_phone(client, settings, owner, condition="used")

        row = (await ageing(client, owner.auth, days=0))["data"][0]

        assert row["askingPrice"] is None
        assert row["impliedMargin"] is None
        assert row["acquisitionCostMinor"] == 38000

    async def test_only_reductions_count_as_markdowns(self, client, settings, owner):
        """FR-9.4 counts how many times it was *marked down*. The first
        pricing is not a markdown, and neither is a raise."""
        unit_id, _, _ = await receive_phone(client, settings, owner)
        await reprice(client, owner, unit_id, "420")
        await reprice(client, owner, unit_id, "390")
        await reprice(client, owner, unit_id, "360")
        await reprice(client, owner, unit_id, "400")

        row = (await ageing(client, owner.auth, days=0))["data"][0]

        assert row["markdownCount"] == 2

    async def test_a_handset_younger_than_the_window_is_not_ageing(
        self, client, settings, owner
    ):
        await receive_phone(client, settings, owner)

        assert (await ageing(client, owner.auth, days=30))["totalItems"] == 0

    async def test_a_sold_handset_leaves_the_report(self, client, settings, owner):
        """Ageing is about what is still on the shelf."""
        unit_id, _, location_id = await receive_phone(client, settings, owner)
        await reprice(client, owner, unit_id, "500")
        created = await client.post(
            "/api/v1/invoices", headers=owner.auth, json={"locationId": str(location_id)}
        )
        invoice_id = created.json()["data"]["id"]
        await client.post(
            f"/api/v1/invoices/{invoice_id}/scan",
            headers=owner.auth,
            json={"code": PHONE_IMEI},
        )
        confirmed = await client.post(
            f"/api/v1/invoices/{invoice_id}/confirm", headers=owner.auth
        )
        assert confirmed.status_code == 200, confirmed.text

        assert (await ageing(client, owner.auth, days=0))["totalItems"] == 0

    async def test_sorting_by_markdowns_puts_the_most_cut_first(
        self, client, settings, owner
    ):
        untouched, _, _ = await receive_phone(client, settings, owner)
        cut, _, _ = await receive_phone(client, settings, owner, imei=SECOND_IMEI)
        await reprice(client, owner, untouched, "500")
        await reprice(client, owner, cut, "500")
        await reprice(client, owner, cut, "450")

        body = await ageing(client, owner.auth, days=0, sort="markdowns")

        assert [row["deviceUnitId"] for row in body["data"]] == [
            str(cut),
            str(untouched),
        ]
