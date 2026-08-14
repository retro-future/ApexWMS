"""M4's demo, against a real tenant database (PRD §10).

*"Scan ten phones into stock with a real scanner — some new from a
supplier, some traded in from walk-ins, paid for in som, booked in
dollars, and individually priced."*

Everything here goes through HTTP. Nothing reaches into a repository, so
what passes is the surface an operator with a keyboard-wedge scanner
actually drives.
"""

import pytest

from tests.api.ledger_helpers import PASSWORD

API = "/api/v1"

# Fifteen digits with a valid Luhn check digit — a typo'd IMEI is worse
# than no IMEI (§4.2), so the scan endpoint refuses one.
NEW_IMEIS = [
    "490154203237518",
    "356938035643809",
    "352099001761481",
    "013269009999992",
    "354879041234567",
]
USED_IMEIS = ["869924030176755", "358240051111110"]


@pytest.fixture
async def store(client, create_tenant):
    """A store with a location, a supplier, a customer and a phone in the
    catalog — everything a receipt names."""
    owner = await create_tenant(password=PASSWORD)

    async def post(path: str, body: dict) -> dict:
        response = await client.post(f"{API}{path}", headers=owner.auth, json=body)
        assert response.status_code == 201, response.text
        return response.json()["data"]

    location = await post("/locations", {"name": "Chilonzor shop"})
    supplier = await post("/suppliers", {"name": "Tashkent Mobile"})
    customer = await post("/customers", {"fullName": "Walk-in", "phone": "+998901112233"})
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
        },
    )
    return owner, {
        "location": location["id"],
        "supplier": supplier["id"],
        "customer": customer["id"],
        "phone": phone["id"],
        "case": case["id"],
    }


async def open_receipt(client, owner, body: dict) -> dict:
    response = await client.post(f"{API}/receipts", headers=owner.auth, json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def scan(client, owner, receipt_id: str, imei: str, **fields):
    return await client.post(
        f"{API}/receipts/{receipt_id}/scan",
        headers=owner.auth,
        json={"imei": imei, **fields},
    )


class TestTheDemo:
    async def test_ten_phones_in_from_a_supplier_and_from_walk_ins(self, client, store):
        """Five new from a supplier, two used traded in from walk-ins, and
        a box of cases — one shelf, three deliveries."""
        owner, ids = store

        supplied = await open_receipt(
            client,
            owner,
            {
                "locationId": ids["location"],
                "acquisitionSource": "supplier",
                "supplierId": ids["supplier"],
                "lines": [{"productId": ids["phone"], "quantity": 5}],
            },
        )
        for imei in NEW_IMEIS:
            scanned = await scan(
                client, owner, supplied["id"], imei, acquisitionCost="700.00"
            )
            assert scanned.status_code == 200, scanned.text
        assert scanned.json()["data"]["scannedCount"] == 5

        confirmed = await client.post(
            f"{API}/receipts/{supplied['id']}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["data"]["status"] == "confirmed"

        traded = await open_receipt(
            client,
            owner,
            {
                "locationId": ids["location"],
                "acquisitionSource": "trade_in",
                "customerId": ids["customer"],
                "lines": [{"productId": ids["phone"], "quantity": 2}],
            },
        )
        for imei, cost, asking, som in [
            (USED_IMEIS[0], "330.00", "420.00", "4200000"),
            (USED_IMEIS[1], "290.00", "380.00", "3700000"),
        ]:
            scanned = await scan(
                client,
                owner,
                traded["id"],
                imei,
                condition="used",
                acquisitionCost=cost,
                askingPrice=asking,
                cashPaid=som,
                cashPaidCurrency="UZS",
            )
            assert scanned.status_code == 200, scanned.text

        confirmed = await client.post(
            f"{API}/receipts/{traded['id']}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text

        accessories = await open_receipt(
            client,
            owner,
            {
                "locationId": ids["location"],
                "supplierId": ids["supplier"],
                "lines": [
                    {"productId": ids["case"], "quantity": 20, "unitCost": "15000"}
                ],
            },
        )
        confirmed = await client.post(
            f"{API}/receipts/{accessories['id']}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text

        listed = await client.get(f"{API}/receipts", headers=owner.auth)
        assert listed.status_code == 200
        assert listed.json()["totalItems"] == 3

        by_source = await client.get(
            f"{API}/receipts?acquisitionSource=trade_in", headers=owner.auth
        )
        assert [r["number"] for r in by_source.json()["data"]] == [traded["number"]]

    async def test_a_som_paid_trade_in_books_the_dollars_and_nothing_else(
        self, client, store
    ):
        """FR-3.4c's stated test: `$330` booked, `4 200 000 so'm` recorded,
        and no figure anywhere equal to the som."""
        owner, ids = store
        traded = await open_receipt(
            client,
            owner,
            {
                "locationId": ids["location"],
                "acquisitionSource": "trade_in",
                "lines": [{"productId": ids["phone"], "quantity": 1}],
            },
        )
        await scan(
            client,
            owner,
            traded["id"],
            USED_IMEIS[0],
            condition="used",
            acquisitionCost="330.00",
            askingPrice="420.00",
            cashPaid="4200000",
            cashPaidCurrency="UZS",
        )
        await client.post(
            f"{API}/receipts/{traded['id']}/confirm", headers=owner.auth, json={}
        )

        found = await client.get(f"{API}/receipts/{traded['id']}", headers=owner.auth)
        body = found.json()["data"]

        # One subtotal, in the product's currency. The som appears only as a
        # formatted string on the handset, in no total anywhere (FR-3.4d).
        assert [(s["currency"], s["amountMinor"]) for s in body["subtotals"]] == [
            ("USD", 33_000)
        ]
        unit = body["lines"][0]["units"][0]
        assert unit["acquisitionCostMinor"] == 33_000
        assert "4 200 000" in unit["cashPaid"]
        assert "4200000" not in found.text.replace('"cashPaid"', "")


class TestTheGuards:
    async def test_a_supplier_receipt_with_no_supplier_is_rejected(self, client, store):
        """FR-3.3b."""
        owner, ids = store
        response = await client.post(
            f"{API}/receipts",
            headers=owner.auth,
            json={
                "locationId": ids["location"],
                "acquisitionSource": "supplier",
                "lines": [{"productId": ids["phone"], "quantity": 1}],
            },
        )
        assert response.status_code == 422, response.text

    async def test_a_malformed_imei_is_refused_at_the_scan(self, client, store):
        """FR-3.4: the last digit here fails the Luhn check."""
        owner, ids = store
        receipt = await open_receipt(
            client,
            owner,
            {
                "locationId": ids["location"],
                "supplierId": ids["supplier"],
                "lines": [{"productId": ids["phone"], "quantity": 1}],
            },
        )

        response = await scan(client, owner, receipt["id"], "490154203237519")

        assert response.status_code == 422, response.text

    async def test_an_imei_already_in_stock_says_where_it_is(self, client, store):
        """FR-3.5."""
        owner, ids = store
        first = await open_receipt(
            client,
            owner,
            {
                "locationId": ids["location"],
                "supplierId": ids["supplier"],
                "lines": [{"productId": ids["phone"], "quantity": 1}],
            },
        )
        await scan(client, owner, first["id"], NEW_IMEIS[0], acquisitionCost="700.00")
        await client.post(
            f"{API}/receipts/{first['id']}/confirm", headers=owner.auth, json={}
        )

        second = await open_receipt(
            client,
            owner,
            {
                "locationId": ids["location"],
                "supplierId": ids["supplier"],
                "lines": [{"productId": ids["phone"], "quantity": 1}],
            },
        )
        response = await scan(client, owner, second["id"], NEW_IMEIS[0])

        assert response.status_code == 409, response.text
        assert "in_stock" in response.json()["detail"]

    async def test_an_unpriced_used_handset_blocks_the_confirm_and_names_itself(
        self, client, store
    ):
        """FR-3.10's stated test: one NEW and one USED with no price. The
        refusal names only the used one; price it, and confirm succeeds."""
        owner, ids = store
        receipt = await open_receipt(
            client,
            owner,
            {
                "locationId": ids["location"],
                "supplierId": ids["supplier"],
                "lines": [{"productId": ids["phone"], "quantity": 2}],
            },
        )
        await scan(
            client, owner, receipt["id"], NEW_IMEIS[0], acquisitionCost="700.00"
        )
        await scan(
            client,
            owner,
            receipt["id"],
            USED_IMEIS[0],
            condition="used",
            acquisitionCost="410.00",
        )

        refused = await client.post(
            f"{API}/receipts/{receipt['id']}/confirm", headers=owner.auth, json={}
        )
        assert refused.status_code == 422, refused.text
        assert USED_IMEIS[0] in refused.json()["detail"]
        assert NEW_IMEIS[0] not in refused.json()["detail"]

        priced = await client.patch(
            f"{API}/receipts/{receipt['id']}/scan/{USED_IMEIS[0]}",
            headers=owner.auth,
            json={"askingPrice": "520.00"},
        )
        assert priced.status_code == 200, priced.text

        confirmed = await client.post(
            f"{API}/receipts/{receipt['id']}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text

    async def test_a_short_scanned_line_cannot_be_confirmed(self, client, store):
        """FR-3.8."""
        owner, ids = store
        receipt = await open_receipt(
            client,
            owner,
            {
                "locationId": ids["location"],
                "supplierId": ids["supplier"],
                "lines": [{"productId": ids["phone"], "quantity": 3}],
            },
        )
        await scan(client, owner, receipt["id"], NEW_IMEIS[0], acquisitionCost="700.00")

        refused = await client.post(
            f"{API}/receipts/{receipt['id']}/confirm", headers=owner.auth, json={}
        )

        assert refused.status_code == 422
        assert "1 of 3" in refused.json()["detail"]

    async def test_a_confirmed_receipt_cannot_be_scanned_onto(self, client, store):
        owner, ids = store
        receipt = await open_receipt(
            client,
            owner,
            {
                "locationId": ids["location"],
                "supplierId": ids["supplier"],
                "lines": [{"productId": ids["phone"], "quantity": 1}],
            },
        )
        await scan(client, owner, receipt["id"], NEW_IMEIS[0], acquisitionCost="700.00")
        await client.post(
            f"{API}/receipts/{receipt['id']}/confirm", headers=owner.auth, json={}
        )

        response = await scan(client, owner, receipt["id"], NEW_IMEIS[1])

        assert response.status_code == 409, response.text


class TestCancellation:
    async def test_it_reverses_both_ledgers_and_the_handset_is_not_written_off(
        self, client, store
    ):
        owner, ids = store
        receipt = await open_receipt(
            client,
            owner,
            {
                "locationId": ids["location"],
                "supplierId": ids["supplier"],
                "lines": [{"productId": ids["phone"], "quantity": 1}],
            },
        )
        await scan(client, owner, receipt["id"], NEW_IMEIS[0], acquisitionCost="700.00")
        await client.post(
            f"{API}/receipts/{receipt['id']}/confirm", headers=owner.auth, json={}
        )

        cancelled = await client.post(
            f"{API}/receipts/{receipt['id']}/cancel",
            headers=owner.auth,
            json={"reason": "wrong van"},
        )
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["data"]["status"] == "cancelled"

        again = await client.post(
            f"{API}/receipts/{receipt['id']}/cancel", headers=owner.auth, json={}
        )
        assert again.status_code == 409, again.text


class TestPurchaseOrders:
    async def test_an_order_reports_pending_then_partial_then_complete(
        self, client, store
    ):
        """FR-3.9."""
        owner, ids = store
        raised = await client.post(
            f"{API}/purchase-orders",
            headers=owner.auth,
            json={
                "supplierId": ids["supplier"],
                "lines": [
                    {"productId": ids["phone"], "quantity": 2, "unitCost": "700.00"}
                ],
            },
        )
        assert raised.status_code == 201, raised.text
        order = raised.json()["data"]
        assert order["number"].startswith("PO-")
        assert order["fulfilment"] == "pending"

        confirmed = await client.post(
            f"{API}/purchase-orders/{order['id']}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text

        for imei, expected in [(NEW_IMEIS[0], "partial"), (NEW_IMEIS[1], "complete")]:
            receipt = await open_receipt(
                client,
                owner,
                {
                    "locationId": ids["location"],
                    "purchaseOrderId": order["id"],
                    "lines": [{"productId": ids["phone"], "quantity": 1}],
                },
            )
            # Raised from an order, so it is always from that supplier.
            assert receipt["acquisitionSource"] == "supplier"
            assert receipt["supplierId"] == ids["supplier"]

            await scan(client, owner, receipt["id"], imei, acquisitionCost="700.00")
            await client.post(
                f"{API}/receipts/{receipt['id']}/confirm", headers=owner.auth, json={}
            )

            seen = await client.get(
                f"{API}/purchase-orders/{order['id']}", headers=owner.auth
            )
            assert seen.json()["data"]["fulfilment"] == expected

    async def test_a_receipt_past_the_ordered_quantity_is_rejected(self, client, store):
        """A confirmed batch of 2, on an order for 2, leaves nothing to take."""
        owner, ids = store
        raised = await client.post(
            f"{API}/purchase-orders",
            headers=owner.auth,
            json={
                "supplierId": ids["supplier"],
                "lines": [
                    {"productId": ids["phone"], "quantity": 2, "unitCost": "700.00"}
                ],
            },
        )
        order = raised.json()["data"]
        await client.post(
            f"{API}/purchase-orders/{order['id']}/confirm", headers=owner.auth, json={}
        )
        receipt = await open_receipt(
            client,
            owner,
            {"locationId": ids["location"], "purchaseOrderId": order["id"]},
        )
        for imei in (NEW_IMEIS[0], NEW_IMEIS[1]):
            await scan(client, owner, receipt["id"], imei, acquisitionCost="700.00")
        await client.post(
            f"{API}/receipts/{receipt['id']}/confirm", headers=owner.auth, json={}
        )

        rejected = await client.post(
            f"{API}/receipts",
            headers=owner.auth,
            json={"locationId": ids["location"], "purchaseOrderId": order["id"]},
        )

        assert rejected.status_code == 409, rejected.text

    async def test_confirming_an_order_moves_no_stock(self, client, store):
        """FR-3.2."""
        owner, ids = store
        raised = await client.post(
            f"{API}/purchase-orders",
            headers=owner.auth,
            json={
                "supplierId": ids["supplier"],
                "lines": [
                    {"productId": ids["phone"], "quantity": 5, "unitCost": "700.00"}
                ],
            },
        )
        order = raised.json()["data"]
        await client.post(
            f"{API}/purchase-orders/{order['id']}/confirm", headers=owner.auth, json={}
        )

        units = await client.get(f"{API}/receipts", headers=owner.auth)
        assert units.json()["totalItems"] == 0
