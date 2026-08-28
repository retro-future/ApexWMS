"""Supplier returns and write-offs against a real tenant database (PRD §5.5, §5.6).

Everything here goes through HTTP. The two documents share a suite because
they share a poster, and the thing most worth proving over a real database
is that they still land in different terminal statuses and different
financial categories — §5.10 reads them in different columns.
"""

import pytest

from tests.api.ledger_helpers import PASSWORD
from tests.api.pdf_helpers import pdf_text

API = "/api/v1"

IMEIS = ["490154203237518", "356938035643809", "352099001761481"]


@pytest.fixture
async def store(client, create_tenant):
    """A store with three phones and a box of cases in stock."""
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
            "defaultSalePrice": "50000",
            "barcode": "4006381333931",
        },
    )

    receipt = await post(
        "/receipts",
        {
            "locationId": location["id"],
            "acquisitionSource": "supplier",
            "supplierId": supplier["id"],
            "lines": [
                {"productId": phone["id"], "quantity": 3},
                {"productId": case["id"], "quantity": 10, "unitCost": "30000"},
            ],
        },
    )
    for imei in IMEIS:
        scanned = await client.post(
            f"{API}/receipts/{receipt['id']}/scan",
            headers=owner.auth,
            json={"imei": imei, "acquisitionCost": "700.00"},
        )
        assert scanned.status_code == 200, scanned.text
    confirmed = await client.post(
        f"{API}/receipts/{receipt['id']}/confirm", headers=owner.auth, json={}
    )
    assert confirmed.status_code == 200, confirmed.text

    return owner, {
        "location": location["id"],
        "supplier": supplier["id"],
        "phone": phone["id"],
        "case": case["id"],
    }


async def open_return(client, owner, ids, reason: str = "defective") -> dict:
    response = await client.post(
        f"{API}/supplier-returns",
        headers=owner.auth,
        json={
            "supplierId": ids["supplier"],
            "locationId": ids["location"],
            "reason": reason,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def open_write_off(client, owner, ids, reason: str = "damage") -> dict:
    response = await client.post(
        f"{API}/write-offs",
        headers=owner.auth,
        json={"locationId": ids["location"], "reason": reason},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def a_confirmed_return(client, owner, ids) -> dict:
    document = await open_return(client, owner, ids)
    for imei in IMEIS[:2]:
        beeped = await client.post(
            f"{API}/supplier-returns/{document['id']}/scan",
            headers=owner.auth,
            json={"code": imei},
        )
        assert beeped.status_code == 200, beeped.text
    confirmed = await client.post(
        f"{API}/supplier-returns/{document['id']}/confirm", headers=owner.auth, json={}
    )
    assert confirmed.status_code == 200, confirmed.text
    return document


async def unit_by_imei(client, auth, imei: str) -> dict:
    found = await client.get(f"{API}/scan/lookup", headers=auth, params={"code": imei})
    assert found.status_code == 200, found.text
    return found.json()["data"]["device"]


class TestSendingGoodsBack:
    async def test_scan_two_phones_back_and_confirm(self, client, store):
        owner, ids = store
        document = await open_return(client, owner, ids)
        assert document["number"].startswith("SR-")

        for imei in IMEIS[:2]:
            beeped = await client.post(
                f"{API}/supplier-returns/{document['id']}/scan",
                headers=owner.auth,
                json={"code": imei},
            )
            assert beeped.status_code == 200, beeped.text
        assert beeped.json()["data"]["lineCount"] == 2

        confirmed = await client.post(
            f"{API}/supplier-returns/{document['id']}/confirm",
            headers=owner.auth,
            json={},
        )

        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["data"]["status"] == "confirmed"
        for imei in IMEIS[:2]:
            assert (await unit_by_imei(client, owner.auth, imei))[
                "status"
            ] == "returned_to_supplier"

    async def test_a_sold_handset_cannot_also_go_back(self, client, store):
        """FR-5.2, refused on the scan that named it (§6)."""
        owner, ids = store
        invoice = await client.post(
            f"{API}/invoices", headers=owner.auth, json={"locationId": ids["location"]}
        )
        await client.post(
            f"{API}/invoices/{invoice.json()['data']['id']}/scan",
            headers=owner.auth,
            json={"code": IMEIS[0]},
        )
        sold = await client.post(
            f"{API}/invoices/{invoice.json()['data']['id']}/confirm",
            headers=owner.auth,
            json={"paymentType": "paid_in_full"},
        )
        assert sold.status_code == 200, sold.text

        document = await open_return(client, owner, ids)
        refused = await client.post(
            f"{API}/supplier-returns/{document['id']}/scan",
            headers=owner.auth,
            json={"code": IMEIS[0]},
        )

        assert refused.status_code == 409
        assert "sold" in refused.json()["detail"]

    async def test_a_phone_from_another_supplier_is_refused(self, client, store):
        """FR-5.2b, over a real receipt: origin is the receipt that stocked it."""
        owner, ids = store
        other = await client.post(
            f"{API}/suppliers", headers=owner.auth, json={"name": "Samarkand Mobile"}
        )
        assert other.status_code == 201, other.text
        document = await open_return(
            client, owner, {**ids, "supplier": other.json()["data"]["id"]}
        )

        refused = await client.post(
            f"{API}/supplier-returns/{document['id']}/scan",
            headers=owner.auth,
            json={"code": IMEIS[0]},
        )

        assert refused.status_code == 409, refused.text
        assert "another supplier" in refused.json()["detail"]

    async def test_a_scan_comes_off_a_draft(self, client, store):
        owner, ids = store
        document = await open_return(client, owner, ids)
        await client.post(
            f"{API}/supplier-returns/{document['id']}/scan",
            headers=owner.auth,
            json={"code": IMEIS[0]},
        )

        removed = await client.delete(
            f"{API}/supplier-returns/{document['id']}/scan/{IMEIS[0]}",
            headers=owner.auth,
        )

        assert removed.status_code == 200, removed.text
        read = await client.get(
            f"{API}/supplier-returns/{document['id']}", headers=owner.auth
        )
        assert read.json()["data"]["lineCount"] == 0

    async def test_an_empty_return_will_not_confirm(self, client, store):
        owner, ids = store
        document = await open_return(client, owner, ids)

        refused = await client.post(
            f"{API}/supplier-returns/{document['id']}/confirm",
            headers=owner.auth,
            json={},
        )

        assert refused.status_code == 422

    async def test_returns_are_filterable_by_reason(self, client, store):
        """FR-5.1's closed set is what makes this a query rather than a trawl
        through free-text notes."""
        owner, ids = store
        await open_return(client, owner, ids, reason="defective")
        await open_return(client, owner, ids, reason="unsold")

        listed = await client.get(
            f"{API}/supplier-returns", headers=owner.auth, params={"reason": "unsold"}
        )

        assert listed.status_code == 200, listed.text
        rows = listed.json()["data"]
        assert len(rows) == 1
        assert rows[0]["reason"] == "unsold"


class TestWritingStockOff:
    async def test_a_broken_phone_is_written_off(self, client, store):
        owner, ids = store
        document = await open_write_off(client, owner, ids, reason="damage")
        assert document["number"].startswith("WO-")

        await client.post(
            f"{API}/write-offs/{document['id']}/scan",
            headers=owner.auth,
            json={"code": IMEIS[0]},
        )
        confirmed = await client.post(
            f"{API}/write-offs/{document['id']}/confirm", headers=owner.auth, json={}
        )

        assert confirmed.status_code == 200, confirmed.text
        assert (await unit_by_imei(client, owner.auth, IMEIS[0]))[
            "status"
        ] == "written_off"

    async def test_a_box_of_cases_is_written_off_by_barcode(self, client, store):
        owner, ids = store
        document = await open_write_off(client, owner, ids, reason="damage")

        for _ in range(3):
            beeped = await client.post(
                f"{API}/write-offs/{document['id']}/scan",
                headers=owner.auth,
                json={"code": "4006381333931"},
            )
            assert beeped.status_code == 200, beeped.text
        # Three damaged cases are three items, not one line scanned thrice.
        assert beeped.json()["data"]["lines"][0]["quantity"] == 3

        confirmed = await client.post(
            f"{API}/write-offs/{document['id']}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text

    async def test_write_offs_are_filterable_by_reason(self, client, store):
        """FR-6.5: "what did theft cost us this quarter" is the question."""
        owner, ids = store
        await open_write_off(client, owner, ids, reason="damage")
        await open_write_off(client, owner, ids, reason="theft")

        listed = await client.get(
            f"{API}/write-offs", headers=owner.auth, params={"reason": "theft"}
        )

        assert listed.status_code == 200, listed.text
        assert [row["reason"] for row in listed.json()["data"]] == ["theft"]

    async def test_a_written_off_phone_that_turns_up_comes_back(self, client, store):
        owner, ids = store
        document = await open_write_off(client, owner, ids, reason="loss")
        await client.post(
            f"{API}/write-offs/{document['id']}/scan",
            headers=owner.auth,
            json={"code": IMEIS[0]},
        )
        await client.post(
            f"{API}/write-offs/{document['id']}/confirm", headers=owner.auth, json={}
        )

        cancelled = await client.post(
            f"{API}/write-offs/{document['id']}/cancel",
            headers=owner.auth,
            json={"reason": "found behind the counter"},
        )

        assert cancelled.status_code == 200, cancelled.text
        back = await unit_by_imei(client, owner.auth, IMEIS[0])
        assert back["status"] == "in_stock"
        assert back["locationId"] == ids["location"]


class TestTheReturnNotePrints:
    async def test_a_confirmed_return_renders_a_pdf(self, client, store):
        """FR-5.3, FR-8.1, FR-8.2: the goods going back, named by IMEI."""
        owner, ids = store
        await client.put(
            f"{API}/settings/tenant",
            headers=owner.auth,
            json={
                "timezone": "Asia/Tashkent",
                "businessName": "Apex Mobile",
                "address": "12 Amir Temur, Tashkent",
            },
        )
        document = await a_confirmed_return(client, owner, ids)

        printed = await client.get(
            f"{API}/supplier-returns/{document['id']}/pdf", headers=owner.auth
        )

        assert printed.status_code == 200, printed.text
        assert printed.headers["content-type"] == "application/pdf"
        page = pdf_text(printed.content)
        assert document["number"] in page
        assert "Apex Mobile" in page
        assert "Tashkent Mobile" in page
        assert "Chilonzor shop" in page
        assert "defective" in page
        assert IMEIS[0] in page
        assert IMEIS[1] in page

    async def test_the_note_carries_no_money(self, client, store):
        """The credited value is a ledger row, not a figure on this page.

        A return note quoting its own number would be a second opinion
        about what the financial ledger already holds.
        """
        owner, ids = store
        document = await a_confirmed_return(client, owner, ids)

        printed = await client.get(
            f"{API}/supplier-returns/{document['id']}/pdf", headers=owner.auth
        )

        page = pdf_text(printed.content)
        assert "700" not in page
        assert "$" not in page
        assert "Total" not in page

    async def test_a_draft_return_has_sent_nothing_back(self, client, store):
        owner, ids = store
        document = await open_return(client, owner, ids)

        printed = await client.get(
            f"{API}/supplier-returns/{document['id']}/pdf", headers=owner.auth
        )

        assert printed.status_code == 409, printed.text

    async def test_it_regenerates_identically(self, client, store):
        """FR-8.3."""
        owner, ids = store
        document = await a_confirmed_return(client, owner, ids)

        first = await client.get(
            f"{API}/supplier-returns/{document['id']}/pdf", headers=owner.auth
        )
        second = await client.get(
            f"{API}/supplier-returns/{document['id']}/pdf", headers=owner.auth
        )

        assert first.content == second.content


class TestNeitherIsASellersJob:
    """§2.1: returning stock and writing it off are Owner/Manager calls."""

    @pytest.fixture
    async def seller(self, client, store):
        owner, ids = store
        invite = await client.post(
            f"{API}/users/invite",
            headers=owner.auth,
            json={"email": "seller@example.com", "role": "tenant.seller"},
        )
        assert invite.status_code == 201, invite.text
        accepted = await client.post(
            f"{API}/auth/accept-invite",
            json={"token": invite.json()["data"]["token"], "password": "sellerpass1"},
        )
        assert accepted.status_code == 201, accepted.text
        login = await client.post(
            f"{API}/auth/login",
            json={"email": "seller@example.com", "password": "sellerpass1"},
        )
        token = login.json()["data"]["accessToken"]
        return {"Authorization": f"Bearer {token}"}, ids

    async def test_a_seller_cannot_open_a_return(self, client, seller):
        auth, ids = seller

        refused = await client.post(
            f"{API}/supplier-returns",
            headers=auth,
            json={
                "supplierId": ids["supplier"],
                "locationId": ids["location"],
                "reason": "defective",
            },
        )

        assert refused.status_code == 403

    async def test_a_seller_cannot_open_a_write_off(self, client, seller):
        auth, ids = seller

        refused = await client.post(
            f"{API}/write-offs",
            headers=auth,
            json={"locationId": ids["location"], "reason": "theft"},
        )

        assert refused.status_code == 403

    async def test_a_seller_cannot_even_read_the_loss_list(self, client, seller):
        auth, _ = seller

        refused = await client.get(f"{API}/write-offs", headers=auth)

        assert refused.status_code == 403


class TestTheReturnRepository:
    """The supplier return is the first aggregate whose lines are added and
    removed by scanning to move to the generic repository (ADR 0007), so
    the mapper syncs the whole collection on every ``update``. These drive
    the parts a fake cannot: currency, tracking type and the scanned IMEI
    come off join rows, a scan inserts one child, an unscan deletes one, a
    repeat barcode bumps a quantity in place."""

    async def _lines(self, client, owner, document_id: str) -> list[dict]:
        response = await client.get(
            f"{API}/supplier-returns/{document_id}", headers=owner.auth
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]["lines"]

    async def _scan(self, client, owner, document_id: str, code: str):
        return await client.post(
            f"{API}/supplier-returns/{document_id}/scan",
            headers=owner.auth,
            json={"code": code},
        )

    async def test_a_scan_inserts_a_line_carrying_its_join_fields(
        self, client, store
    ):
        owner, ids = store
        document = await open_return(client, owner, ids)

        assert (await self._scan(client, owner, document["id"], IMEIS[0])).status_code == 200
        assert (
            await self._scan(client, owner, document["id"], "4006381333931")
        ).status_code == 200

        lines = await self._lines(client, owner, document["id"])
        by_product = {line["productId"]: line for line in lines}
        phone_line = by_product[ids["phone"]]
        assert phone_line["currency"] == "USD"
        assert phone_line["trackingType"] == "serial"
        assert phone_line["imei"] == IMEIS[0]
        case_line = by_product[ids["case"]]
        assert case_line["currency"] == "UZS"
        assert case_line["trackingType"] == "quantity"
        assert case_line["imei"] is None

    async def test_an_unscan_deletes_only_that_line(self, client, store):
        owner, ids = store
        document = await open_return(client, owner, ids)
        await self._scan(client, owner, document["id"], IMEIS[0])
        await self._scan(client, owner, document["id"], IMEIS[1])

        removed = await client.delete(
            f"{API}/supplier-returns/{document['id']}/scan/{IMEIS[0]}",
            headers=owner.auth,
        )
        assert removed.status_code == 200, removed.text

        lines = await self._lines(client, owner, document["id"])
        assert [line["imei"] for line in lines] == [IMEIS[1]]

    async def test_a_repeat_barcode_bumps_the_quantity_in_place(self, client, store):
        owner, ids = store
        document = await open_return(client, owner, ids)

        await self._scan(client, owner, document["id"], "4006381333931")
        await self._scan(client, owner, document["id"], "4006381333931")

        lines = await self._lines(client, owner, document["id"])
        assert len(lines) == 1
        assert lines[0]["quantity"] == 2

    async def test_the_browse_filters_by_reason_and_supplier(self, client, store):
        owner, ids = store
        defective = await open_return(client, owner, ids, reason="defective")
        await open_return(client, owner, ids, reason="unsold")

        async def numbers(query: str) -> set[str]:
            response = await client.get(
                f"{API}/supplier-returns{query}", headers=owner.auth
            )
            assert response.status_code == 200, response.text
            return {row["id"] for row in response.json()["data"]}

        assert await numbers("?reason=defective") == {defective["id"]}
        assert defective["id"] in await numbers(f"?supplierId={ids['supplier']}")
        assert await numbers("?search=NOSUCHNUMBER") == set()
