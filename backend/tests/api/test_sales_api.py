"""Selling over HTTP, against real tables — PRD §5.4, §8.

The application suite proves the rules against fakes. This one proves the
wiring: the migration, the joins that rebuild a line from its product, the
two ledgers on real rows, the roles, and the PDF.

``receive_phone`` puts a **used handset with no asking price** in stock,
which is the state FR-4.2b exists to refuse at the counter and the one the
receiving surface deliberately will not produce.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from application.specs import MovementsForUnit
from domain.enums import DeviceStatus, TransactionType
from domain.value_objects import Currency
from infrastructure.persistence.mappers import StockMovementMapper
from infrastructure.persistence.repositories import TenantSqlAppendOnlyRepository
from infrastructure.persistence.tenant.models import StockMovementModel
from infrastructure.persistence.tenant.queries import SqlFinancialTransactionQueries
from infrastructure.types import TenantSession
from tests.api.ledger_helpers import PHONE_IMEI, receive_phone, tenant_url, usd
from tests.api.pdf_helpers import pdf_text


async def ledger_rows(settings, owner, unit_id):
    """One handset's movements and the store's money totals, read straight
    from the tenant database."""
    engine = create_async_engine(await tenant_url(settings, owner.tenant_id))
    try:
        async with async_sessionmaker(engine)() as raw:
            session = TenantSession(raw)
            repo = TenantSqlAppendOnlyRepository(
                session, StockMovementModel, StockMovementMapper()
            )
            return (
                await repo.find(MovementsForUnit(unit_id)),
                await SqlFinancialTransactionQueries(session).totals_by_type(),
            )
    finally:
        await engine.dispose()


async def open_invoice(client, owner, location_id, **body):
    created = await client.post(
        "/api/v1/invoices",
        headers=owner.auth,
        json={"locationId": str(location_id), **body},
    )
    assert created.status_code == 201, created.text
    return created.json()["data"]


async def price_unit(client, owner, unit_id, amount):
    priced = await client.patch(
        f"/api/v1/device-units/{unit_id}/price",
        headers=owner.auth,
        json={"askingPrice": amount, "reason": "priced for sale"},
    )
    assert priced.status_code == 200, priced.text


class TestTheCounterRefusesAnUnpricedUsedHandset:
    """FR-4.2b end to end, and §11's signature bug held at the HTTP edge."""

    async def test_the_scan_is_rejected_and_names_who_can_fix_it(
        self, client, settings, owner
    ):
        unit_id, product_id, location_id = await receive_phone(client, settings, owner)
        await client.patch(
            f"/api/v1/products/{product_id}",
            headers=owner.auth,
            json={"defaultSalePrice": "900"},
        )
        invoice = await open_invoice(client, owner, location_id)

        scanned = await client.post(
            f"/api/v1/invoices/{invoice['id']}/scan",
            headers=owner.auth,
            json={"code": "490154203237518"},
        )

        assert scanned.status_code == 409, scanned.text
        assert "Owner or Manager" in scanned.json()["detail"]

    async def test_and_the_invoice_is_still_empty(self, client, settings, owner):
        unit_id, product_id, location_id = await receive_phone(client, settings, owner)
        await client.patch(
            f"/api/v1/products/{product_id}",
            headers=owner.auth,
            json={"defaultSalePrice": "900"},
        )
        invoice = await open_invoice(client, owner, location_id)
        await client.post(
            f"/api/v1/invoices/{invoice['id']}/scan",
            headers=owner.auth,
            json={"code": "490154203237518"},
        )

        read = await client.get(f"/api/v1/invoices/{invoice['id']}", headers=owner.auth)

        assert read.json()["data"]["lines"] == []

    async def test_pricing_the_handset_makes_it_sellable_at_its_own_price(
        self, client, settings, owner
    ):
        unit_id, product_id, location_id = await receive_phone(client, settings, owner)
        await client.patch(
            f"/api/v1/products/{product_id}",
            headers=owner.auth,
            json={"defaultSalePrice": "900"},
        )
        await price_unit(client, owner, unit_id, "500")
        invoice = await open_invoice(client, owner, location_id)

        scanned = await client.post(
            f"/api/v1/invoices/{invoice['id']}/scan",
            headers=owner.auth,
            json={"code": "490154203237518"},
        )

        assert scanned.status_code == 200, scanned.text
        assert scanned.json()["data"]["resolvedPriceMinor"] == 50000


class TestSellingAPhoneAndCancellingIt:
    """M5's demo: scan a phone, sell it, cancel, watch both reverse."""

    async def test_confirming_writes_goods_and_money_together(
        self, client, settings, owner
    ):
        unit_id, _, location_id = await receive_phone(client, settings, owner, cost="380")
        await price_unit(client, owner, unit_id, "520")
        invoice = await open_invoice(client, owner, location_id)
        await client.post(
            f"/api/v1/invoices/{invoice['id']}/scan",
            headers=owner.auth,
            json={"code": "490154203237518"},
        )

        confirmed = await client.post(
            f"/api/v1/invoices/{invoice['id']}/confirm", headers=owner.auth
        )

        assert confirmed.status_code == 200, confirmed.text
        data = confirmed.json()["data"]
        assert data["status"] == "confirmed"
        assert data["lines"][0]["chargedPriceMinor"] == 52000
        assert data["subtotals"] == [
            {"currency": "USD", "amount": "520.00", "amountMinor": 52000}
        ]

        movements, totals = await ledger_rows(settings, owner, unit_id)
        assert [m.quantity_delta for m in movements] == [1, -1]
        assert totals[(TransactionType.SALE_REVENUE, Currency.USD)] == usd("520")
        assert totals[(TransactionType.COGS, Currency.USD)] == usd("-380")

    async def test_cancelling_reverses_both_and_returns_the_handset(
        self, client, settings, owner
    ):
        unit_id, _, location_id = await receive_phone(client, settings, owner, cost="380")
        await price_unit(client, owner, unit_id, "520")
        invoice = await open_invoice(client, owner, location_id)
        await client.post(
            f"/api/v1/invoices/{invoice['id']}/scan",
            headers=owner.auth,
            json={"code": "490154203237518"},
        )
        await client.post(f"/api/v1/invoices/{invoice['id']}/confirm", headers=owner.auth)

        cancelled = await client.post(
            f"/api/v1/invoices/{invoice['id']}/cancel",
            headers=owner.auth,
            json={"reason": "customer changed their mind"},
        )

        assert cancelled.status_code == 200, cancelled.text
        movements, totals = await ledger_rows(settings, owner, unit_id)
        # The sale's rows stay and their negation is appended (§4.3 rule 2).
        assert [m.quantity_delta for m in movements] == [1, -1, 1]
        assert totals[(TransactionType.SALE_REVENUE, Currency.USD)] == usd("0")
        assert totals[(TransactionType.COGS, Currency.USD)] == usd("0")

        unit = await client.get(f"/api/v1/device-units/{unit_id}", headers=owner.auth)
        assert unit.json()["data"]["status"] == DeviceStatus.IN_STOCK.value
        # An invoice-line override never repriced it, and a cancel cannot
        # either (FR-4.5).
        assert unit.json()["data"]["resolvedPriceMinor"] == 52000

    async def test_a_sold_handset_cannot_be_sold_again(self, client, settings, owner):
        unit_id, _, location_id = await receive_phone(client, settings, owner)
        await price_unit(client, owner, unit_id, "520")
        first = await open_invoice(client, owner, location_id)
        await client.post(
            f"/api/v1/invoices/{first['id']}/scan",
            headers=owner.auth,
            json={"code": "490154203237518"},
        )
        await client.post(f"/api/v1/invoices/{first['id']}/confirm", headers=owner.auth)

        second = await open_invoice(client, owner, location_id)
        rescanned = await client.post(
            f"/api/v1/invoices/{second['id']}/scan",
            headers=owner.auth,
            json={"code": "490154203237518"},
        )

        assert rescanned.status_code == 409, rescanned.text
        assert "sold" in rescanned.json()["detail"]


class TestAConfirmedInvoiceIsImmutable:
    """FR-4.5d: a wrong confirmed invoice is cancelled and re-entered."""

    async def test_patching_a_line_is_rejected_with_no_side_effect(
        self, client, settings, owner
    ):
        unit_id, _, location_id = await receive_phone(client, settings, owner)
        await price_unit(client, owner, unit_id, "520")
        invoice = await open_invoice(client, owner, location_id)
        scanned = await client.post(
            f"/api/v1/invoices/{invoice['id']}/scan",
            headers=owner.auth,
            json={"code": "490154203237518"},
        )
        line_id = scanned.json()["data"]["line"]["id"]
        await client.post(f"/api/v1/invoices/{invoice['id']}/confirm", headers=owner.auth)
        before = (
            await client.get(f"/api/v1/invoices/{invoice['id']}", headers=owner.auth)
        ).json()
        movements_before, totals_before = await ledger_rows(settings, owner, unit_id)

        patched = await client.patch(
            f"/api/v1/invoices/{invoice['id']}/lines/{line_id}",
            headers=owner.auth,
            json={"price": "1"},
        )

        assert patched.status_code == 409, patched.text
        after = (
            await client.get(f"/api/v1/invoices/{invoice['id']}", headers=owner.auth)
        ).json()
        movements_after, totals_after = await ledger_rows(settings, owner, unit_id)
        assert after == before
        assert len(movements_after) == len(movements_before)
        assert totals_after == totals_before


class TestOverridingAPriceCarriesItsApprover:
    async def test_the_line_reports_both_prices_and_the_manager_who_approved(
        self, client, settings, owner
    ):
        """FR-4.5f, over HTTP with a real employees foreign key."""
        unit_id, _, location_id = await receive_phone(client, settings, owner)
        await price_unit(client, owner, unit_id, "520")
        invoice = await open_invoice(client, owner, location_id)
        scanned = await client.post(
            f"/api/v1/invoices/{invoice['id']}/scan",
            headers=owner.auth,
            json={"code": "490154203237518"},
        )
        line_id = scanned.json()["data"]["line"]["id"]

        overridden = await client.patch(
            f"/api/v1/invoices/{invoice['id']}/lines/{line_id}",
            headers=owner.auth,
            json={"price": "300", "note": "haggled hard"},
        )
        assert overridden.status_code == 200, overridden.text
        confirmed = await client.post(
            f"/api/v1/invoices/{invoice['id']}/confirm", headers=owner.auth
        )

        line = confirmed.json()["data"]["lines"][0]
        assert line["resolvedPriceMinor"] == 52000
        assert line["chargedPriceMinor"] == 30000
        assert line["priceApprovedBy"] == owner.user_id
        assert line["priceNote"] == "haggled hard"
        assert line["isDeviation"] is True

        _, totals = await ledger_rows(settings, owner, unit_id)
        assert totals[(TransactionType.SALE_REVENUE, Currency.USD)] == usd("300")


class TestWhoMaySell:
    """§2.1's matrix, and the rule that a 403 leaves no side effect."""

    async def test_a_seller_may_open_and_confirm_but_not_override_or_cancel(
        self, client, settings, owner, create_tenant
    ):
        unit_id, _, location_id = await receive_phone(client, settings, owner)
        await price_unit(client, owner, unit_id, "520")

        invite = await client.post(
            "/api/v1/users/invite",
            headers=owner.auth,
            json={"email": "seller@example.com", "role": "tenant.seller"},
        )
        assert invite.status_code == 201, invite.text
        await client.post(
            "/api/v1/auth/accept-invite",
            json={"token": invite.json()["data"]["token"], "password": "sellerpass1"},
        )
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "seller@example.com", "password": "sellerpass1"},
        )
        seller = {"Authorization": f"Bearer {login.json()['data']['accessToken']}"}

        created = await client.post(
            "/api/v1/invoices", headers=seller, json={"locationId": str(location_id)}
        )
        assert created.status_code == 201, created.text
        invoice_id = created.json()["data"]["id"]
        scanned = await client.post(
            f"/api/v1/invoices/{invoice_id}/scan",
            headers=seller,
            json={"code": "490154203237518"},
        )
        assert scanned.status_code == 200, scanned.text
        line_id = scanned.json()["data"]["line"]["id"]

        # FR-4.5: a Seller's invoice sells at the resolved price, unchanged.
        refused = await client.patch(
            f"/api/v1/invoices/{invoice_id}/lines/{line_id}",
            headers=seller,
            json={"price": "100"},
        )
        assert refused.status_code == 403
        read = await client.get(f"/api/v1/invoices/{invoice_id}", headers=seller)
        assert read.json()["data"]["lines"][0]["overridePriceMinor"] is None

        confirmed = await client.post(
            f"/api/v1/invoices/{invoice_id}/confirm", headers=seller
        )
        assert confirmed.status_code == 200, confirmed.text

        cancelled = await client.post(
            f"/api/v1/invoices/{invoice_id}/cancel", headers=seller, json={}
        )
        assert cancelled.status_code == 403
        still = await client.get(f"/api/v1/invoices/{invoice_id}", headers=seller)
        assert still.json()["data"]["status"] == "confirmed"


async def a_sold_phone(client, settings, owner) -> dict:
    """A confirmed invoice for one handset, under a store with a letterhead."""
    unit_id, _, location_id = await receive_phone(client, settings, owner)
    await price_unit(client, owner, unit_id, "520")
    await client.put(
        "/api/v1/settings/tenant",
        headers=owner.auth,
        json={
            "timezone": "Asia/Tashkent",
            "businessName": "Apex Mobile",
            "address": "12 Amir Temur, Tashkent",
        },
    )
    invoice = await open_invoice(client, owner, location_id)
    await client.post(
        f"/api/v1/invoices/{invoice['id']}/scan",
        headers=owner.auth,
        json={"code": PHONE_IMEI},
    )
    confirmed = await client.post(
        f"/api/v1/invoices/{invoice['id']}/confirm", headers=owner.auth
    )
    assert confirmed.status_code == 200, confirmed.text
    return invoice


class TestTheInvoicePrints:
    async def test_a_confirmed_sale_renders_a_pdf(self, client, settings, owner):
        """FR-8.1, FR-8.2: a real invoice with an IMEI on it."""
        invoice = await a_sold_phone(client, settings, owner)

        printed = await client.get(
            f"/api/v1/invoices/{invoice['id']}/pdf", headers=owner.auth
        )

        assert printed.status_code == 200, printed.text
        assert printed.headers["content-type"] == "application/pdf"
        assert printed.content.startswith(b"%PDF")
        page = pdf_text(printed.content)
        assert PHONE_IMEI in page
        assert invoice["number"] in page
        assert "Apex Mobile" in page
        assert "$520.00" in page

    async def test_the_page_follows_the_request_locale(self, client, settings, owner):
        invoice = await a_sold_phone(client, settings, owner)

        english = await client.get(
            f"/api/v1/invoices/{invoice['id']}/pdf", headers=owner.auth
        )
        russian = await client.get(
            f"/api/v1/invoices/{invoice['id']}/pdf",
            headers={**owner.auth, "Accept-Language": "ru"},
        )
        uzbek = await client.get(
            f"/api/v1/invoices/{invoice['id']}/pdf",
            headers={**owner.auth, "Accept-Language": "uz"},
        )

        assert "Invoice" in pdf_text(english.content)
        # Cyrillic round-trips through the bundled font's ToUnicode CMap.
        assert "Счёт" in pdf_text(russian.content)
        assert "Hisob-faktura" in pdf_text(uzbek.content)

    async def test_regenerating_it_produces_the_same_file(
        self, client, settings, owner
    ):
        """FR-8.3: immutable once confirmed, byte for byte.

        The one that fails if the renderer ever stamps the wall clock into
        the page instead of the confirm timestamp — which is what fpdf2
        does by default.
        """
        invoice = await a_sold_phone(client, settings, owner)

        first = await client.get(
            f"/api/v1/invoices/{invoice['id']}/pdf", headers=owner.auth
        )
        second = await client.get(
            f"/api/v1/invoices/{invoice['id']}/pdf", headers=owner.auth
        )

        assert first.content == second.content
        # Equal renders one after another prove little on their own — the
        # wall clock barely moves. What makes the file stable a month from
        # now is the date coming off the document.
        read = await client.get(f"/api/v1/invoices/{invoice['id']}", headers=owner.auth)
        confirmed = datetime.fromisoformat(read.json()["data"]["confirmedAt"])
        stamped = confirmed.astimezone(UTC).strftime("D:%Y%m%d%H%M%SZ")
        assert f"/CreationDate ({stamped})".encode() in first.content

    async def test_a_cancelled_sale_still_prints_and_says_so(
        self, client, settings, owner
    ):
        """FR-8.3: cancellation marks the file, it does not remove it."""
        invoice = await a_sold_phone(client, settings, owner)
        cancelled = await client.post(
            f"/api/v1/invoices/{invoice['id']}/cancel",
            headers=owner.auth,
            json={"reason": "customer changed their mind"},
        )
        assert cancelled.status_code == 200, cancelled.text

        printed = await client.get(
            f"/api/v1/invoices/{invoice['id']}/pdf", headers=owner.auth
        )

        assert printed.status_code == 200, printed.text
        page = pdf_text(printed.content)
        assert "CANCELLED" in page
        assert "customer changed their mind" in page
        assert PHONE_IMEI in page

    async def test_a_draft_has_no_prices_to_print(self, client, settings, owner):
        _, _, location_id = await receive_phone(client, settings, owner)
        invoice = await open_invoice(client, owner, location_id)

        printed = await client.get(
            f"/api/v1/invoices/{invoice['id']}/pdf", headers=owner.auth
        )

        assert printed.status_code == 409, printed.text


class TestListingAndLookup:
    async def test_an_unknown_invoice_is_a_404(self, client, owner):
        missing = await client.get(f"/api/v1/invoices/{uuid4()}", headers=owner.auth)
        assert missing.status_code == 404

    async def test_invoices_are_numbered_per_tenant_and_per_year(
        self, client, settings, owner
    ):
        _, _, location_id = await receive_phone(client, settings, owner)
        first = await open_invoice(client, owner, location_id)
        second = await open_invoice(client, owner, location_id)

        assert first["number"].startswith("INV-")
        assert int(second["number"].split("-")[-1]) == int(first["number"].split("-")[-1]) + 1

    async def test_the_list_filters_by_status(self, client, settings, owner):
        unit_id, _, location_id = await receive_phone(client, settings, owner)
        await price_unit(client, owner, unit_id, "520")
        sold = await open_invoice(client, owner, location_id)
        await client.post(
            f"/api/v1/invoices/{sold['id']}/scan",
            headers=owner.auth,
            json={"code": "490154203237518"},
        )
        await client.post(f"/api/v1/invoices/{sold['id']}/confirm", headers=owner.auth)
        await open_invoice(client, owner, location_id)

        confirmed = await client.get(
            "/api/v1/invoices?status=confirmed", headers=owner.auth
        )

        assert confirmed.status_code == 200, confirmed.text
        assert [i["id"] for i in confirmed.json()["data"]] == [sold["id"]]

    async def test_the_search_box_finds_an_invoice_by_imei_or_customer(
        self, client, settings, owner
    ):
        unit_id, _, location_id = await receive_phone(client, settings, owner)
        await price_unit(client, owner, unit_id, "520")
        customer = await client.post(
            "/api/v1/customers",
            headers=owner.auth,
            json={"fullName": "Aziz Karimov", "phone": "+998901112233"},
        )
        assert customer.status_code == 201, customer.text
        customer_id = customer.json()["data"]["id"]

        target = await open_invoice(client, owner, location_id, customerId=customer_id)
        await client.post(
            f"/api/v1/invoices/{target['id']}/scan",
            headers=owner.auth,
            json={"code": "490154203237518"},
        )
        other = await open_invoice(client, owner, location_id)

        for term in ["490154203237518", "Karimov", "901112233"]:
            found = await client.get(
                "/api/v1/invoices", headers=owner.auth, params={"search": term}
            )
            assert found.status_code == 200, found.text
            ids = [i["id"] for i in found.json()["data"]]
            assert ids == [target["id"]], f"search {term!r} returned {ids}"

        by_number = await client.get(
            "/api/v1/invoices", headers=owner.auth, params={"search": other["number"]}
        )
        assert [i["id"] for i in by_number.json()["data"]] == [other["id"]]
