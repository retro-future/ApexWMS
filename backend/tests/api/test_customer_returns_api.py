"""Customer returns against a real tenant database (PRD §5.4b, §8).

Everything here goes through HTTP. The application suite proves the rules
against fakes; this one proves the wiring: the migration, the joins that
rebuild a return line from its product and the invoice line it unwinds, the
two ledgers on real rows, and the roles.

The assertion worth reading twice is the one on ``COGS``. A sale books it
negative and a return books it positive, so a fully returned line nets to
zero — which is what the accessory pool replays to put the goods back at the
value they left it.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from application.specs import MovementsForUnit
from domain.enums import DeviceStatus, TransactionType
from domain.value_objects import Currency
from infrastructure.persistence.mappers import StockMovementMapper
from infrastructure.persistence.repositories import TenantSqlAppendOnlyRepository
from infrastructure.persistence.tenant.models import StockMovementModel
from infrastructure.persistence.tenant.queries import SqlFinancialTransactionQueries
from infrastructure.types import TenantSession
from tests.api.ledger_helpers import PASSWORD, tenant_url, usd

API = "/api/v1"

IMEIS = ["490154203237518", "356938035643809", "352099001761481"]
CASE_BARCODE = "4006381333931"


async def ledger_rows(settings, owner, unit_id):
    """One handset's movements and the store's money totals, from the tenant DB."""
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


@pytest.fixture
async def store(client, create_tenant):
    """A store with three priced phones and ten cases in stock."""
    owner = await create_tenant(password=PASSWORD)

    async def post(path: str, body: dict) -> dict:
        response = await client.post(f"{API}{path}", headers=owner.auth, json=body)
        assert response.status_code == 201, response.text
        return response.json()["data"]

    location = await post("/locations", {"name": "Chilonzor shop"})
    supplier = await post("/suppliers", {"name": "Tashkent Mobile"})
    customer = await post("/customers", {"fullName": "Aziz Karimov"})
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
            "barcode": CASE_BARCODE,
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
        "customer": customer["id"],
        "phone": phone["id"],
        "case": case["id"],
    }


async def sell(client, owner, ids, *, codes=(IMEIS[0],), terms: dict | None = None):
    created = await client.post(
        f"{API}/invoices",
        headers=owner.auth,
        json={"locationId": ids["location"], "customerId": ids["customer"]},
    )
    assert created.status_code == 201, created.text
    invoice = created.json()["data"]
    for code in codes:
        beeped = await client.post(
            f"{API}/invoices/{invoice['id']}/scan",
            headers=owner.auth,
            json={"code": code},
        )
        assert beeped.status_code == 200, beeped.text
    confirmed = await client.post(
        f"{API}/invoices/{invoice['id']}/confirm",
        headers=owner.auth,
        json=terms or {},
    )
    assert confirmed.status_code == 200, confirmed.text
    return confirmed.json()["data"]


async def open_return(client, owner, ids, invoice, reason: str = "defective") -> dict:
    response = await client.post(
        f"{API}/customer-returns",
        headers=owner.auth,
        json={
            "salesInvoiceId": invoice["id"],
            "locationId": ids["location"],
            "reason": reason,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def scan_back(client, auth, document, code: str) -> dict:
    beeped = await client.post(
        f"{API}/customer-returns/{document['id']}/scan",
        headers=auth,
        json={"code": code},
    )
    assert beeped.status_code == 200, beeped.text
    return beeped.json()["data"]


async def unit_by_imei(client, auth, imei: str) -> dict:
    found = await client.get(f"{API}/scan/lookup", headers=auth, params={"code": imei})
    assert found.status_code == 200, found.text
    return found.json()["data"]["device"]


class TestSellAPhoneAndTakeItBack:
    """The §5.4b demo, over real tables."""

    async def test_confirming_moves_goods_and_money_together(
        self, client, settings, store
    ):
        owner, ids = store
        invoice = await sell(client, owner, ids)
        unit = await unit_by_imei(client, owner.auth, IMEIS[0])
        document = await open_return(client, owner, ids, invoice)
        await scan_back(client, owner.auth, document, IMEIS[0])

        confirmed = await client.post(
            f"{API}/customer-returns/{document['id']}/confirm",
            headers=owner.auth,
            json={},
        )

        assert confirmed.status_code == 200, confirmed.text
        data = confirmed.json()["data"]
        assert data["status"] == "confirmed"
        assert data["number"].startswith("CR-")
        assert data["subtotals"] == [
            {"currency": "USD", "amount": "900.00", "amountMinor": 90000}
        ]

        movements, totals = await ledger_rows(settings, owner, unit["id"])
        assert [m.quantity_delta for m in movements] == [1, -1, 1]
        assert totals[(TransactionType.SALE_REVENUE, Currency.USD)] == usd("900")
        assert totals[(TransactionType.SALES_RETURN_REFUND, Currency.USD)] == usd("-900")
        # The sale's -700 and the return's +700 cancel: the goods are back.
        assert totals[(TransactionType.COGS, Currency.USD)] == usd("0")

    async def test_the_handset_is_back_on_the_shelf(self, client, store):
        owner, ids = store
        invoice = await sell(client, owner, ids)
        document = await open_return(client, owner, ids, invoice)
        await scan_back(client, owner.auth, document, IMEIS[0])
        await client.post(
            f"{API}/customer-returns/{document['id']}/confirm",
            headers=owner.auth,
            json={},
        )

        unit = await unit_by_imei(client, owner.auth, IMEIS[0])
        assert unit["status"] == DeviceStatus.IN_STOCK.value
        assert unit["locationId"] == ids["location"]

    async def test_the_line_starts_at_what_the_sale_charged(self, client, store):
        owner, ids = store
        invoice = await sell(client, owner, ids)
        document = await open_return(client, owner, ids, invoice)

        scanned = await scan_back(client, owner.auth, document, IMEIS[0])

        line = scanned["lines"][0]
        assert line["chargedPriceMinor"] == 90000
        assert line["refundPriceMinor"] == 90000
        assert line["soldQuantity"] == 1
        assert line["imei"] == IMEIS[0]
        assert line["isReduced"] is False


class TestGoodsThisSaleNeverSold:
    async def test_another_invoices_handset_is_refused_on_the_scan(
        self, client, store
    ):
        owner, ids = store
        invoice = await sell(client, owner, ids, codes=(IMEIS[0],))
        document = await open_return(client, owner, ids, invoice)

        refused = await client.post(
            f"{API}/customer-returns/{document['id']}/scan",
            headers=owner.auth,
            json={"code": IMEIS[1]},
        )

        assert refused.status_code == 409, refused.text

    async def test_the_same_handset_cannot_come_back_twice(self, client, store):
        owner, ids = store
        invoice = await sell(client, owner, ids)
        first = await open_return(client, owner, ids, invoice)
        await scan_back(client, owner.auth, first, IMEIS[0])
        await client.post(
            f"{API}/customer-returns/{first['id']}/confirm",
            headers=owner.auth,
            json={},
        )

        second = await open_return(client, owner, ids, invoice)
        refused = await client.post(
            f"{API}/customer-returns/{second['id']}/scan",
            headers=owner.auth,
            json={"code": IMEIS[0]},
        )

        assert refused.status_code == 409, refused.text

    async def test_unscanning_by_imei_removes_the_line(self, client, store):
        owner, ids = store
        invoice = await sell(client, owner, ids)
        document = await open_return(client, owner, ids, invoice)
        await scan_back(client, owner.auth, document, IMEIS[0])

        removed = await client.delete(
            f"{API}/customer-returns/{document['id']}/scan/{IMEIS[0]}",
            headers=owner.auth,
        )

        assert removed.status_code == 200, removed.text
        read = await client.get(
            f"{API}/customer-returns/{document['id']}", headers=owner.auth
        )
        assert read.json()["data"]["lineCount"] == 0


class TestKeepingPartOfThePrice:
    """FR-4.9c over HTTP, including the permission escalation."""

    async def test_a_manager_lowers_the_refund_with_a_note(self, client, store):
        owner, ids = store
        invoice = await sell(client, owner, ids)
        document = await open_return(client, owner, ids, invoice)
        scanned = await scan_back(client, owner.auth, document, IMEIS[0])
        line_id = scanned["lines"][0]["id"]

        patched = await client.patch(
            f"{API}/customer-returns/{document['id']}/lines/{line_id}",
            headers=owner.auth,
            json={"refund": "810.00", "note": "opened box, 10% restocking"},
        )

        assert patched.status_code == 200, patched.text
        line = patched.json()["data"]["lines"][0]
        assert line["refundPriceMinor"] == 81000
        assert line["isReduced"] is True
        assert line["refundNote"] == "opened box, 10% restocking"

    async def test_the_kept_amount_never_becomes_revenue(
        self, client, settings, store
    ):
        owner, ids = store
        invoice = await sell(client, owner, ids)
        unit = await unit_by_imei(client, owner.auth, IMEIS[0])
        document = await open_return(client, owner, ids, invoice)
        scanned = await scan_back(client, owner.auth, document, IMEIS[0])
        await client.patch(
            f"{API}/customer-returns/{document['id']}/lines/{scanned['lines'][0]['id']}",
            headers=owner.auth,
            json={"refund": "810.00", "note": "opened box"},
        )

        await client.post(
            f"{API}/customer-returns/{document['id']}/confirm",
            headers=owner.auth,
            json={},
        )

        _, totals = await ledger_rows(settings, owner, unit["id"])
        assert totals[(TransactionType.SALE_REVENUE, Currency.USD)] == usd("900")
        assert totals[(TransactionType.SALES_RETURN_REFUND, Currency.USD)] == usd("-810")

    async def test_refunding_above_the_charge_is_refused(self, client, store):
        owner, ids = store
        invoice = await sell(client, owner, ids)
        document = await open_return(client, owner, ids, invoice)
        scanned = await scan_back(client, owner.auth, document, IMEIS[0])

        refused = await client.patch(
            f"{API}/customer-returns/{document['id']}/lines/{scanned['lines'][0]['id']}",
            headers=owner.auth,
            json={"refund": "1000.00", "note": "generous"},
        )

        assert refused.status_code == 409, refused.text


class TestAPartialAccessoryReturn:
    """§4.6: the pool takes the goods back at the value the sale issued."""

    async def test_one_of_three_cases_comes_back_at_a_third_of_the_cogs(
        self, client, settings, store
    ):
        owner, ids = store
        invoice = await sell(client, owner, ids, codes=(CASE_BARCODE,) * 3)
        document = await open_return(client, owner, ids, invoice)
        await scan_back(client, owner.auth, document, CASE_BARCODE)

        confirmed = await client.post(
            f"{API}/customer-returns/{document['id']}/confirm",
            headers=owner.auth,
            json={},
        )

        assert confirmed.status_code == 200, confirmed.text
        engine = create_async_engine(await tenant_url(settings, owner.tenant_id))
        try:
            async with async_sessionmaker(engine)() as raw:
                totals = await SqlFinancialTransactionQueries(
                    TenantSession(raw)
                ).totals_by_type()
        finally:
            await engine.dispose()

        # Ten cases in at 30 000 each. Three sold: COGS -90 000. One back:
        # +30 000, its exact share of what the sale booked.
        cogs = totals[(TransactionType.COGS, Currency.UZS)]
        assert cogs.amount_minor == -60000
        refund = totals[(TransactionType.SALES_RETURN_REFUND, Currency.UZS)]
        assert refund.amount_minor == -50000

    async def test_returning_a_fourth_case_is_refused(self, client, store):
        owner, ids = store
        invoice = await sell(client, owner, ids, codes=(CASE_BARCODE,) * 3)
        document = await open_return(client, owner, ids, invoice)
        for _ in range(3):
            await scan_back(client, owner.auth, document, CASE_BARCODE)

        refused = await client.post(
            f"{API}/customer-returns/{document['id']}/scan",
            headers=owner.auth,
            json={"code": CASE_BARCODE},
        )

        assert refused.status_code == 409, refused.text


class TestAReturnOnStoreCredit:
    """FR-4.9d: the debt goes down before any cash goes out."""

    CREDIT_TERMS = {
        "paymentType": "store_credit",
        "debt": "11000000",
        "downPayment": "1000000",
    }

    async def test_the_remaining_balance_drops_by_the_relief(self, client, store):
        owner, ids = store
        invoice = await sell(client, owner, ids, terms=self.CREDIT_TERMS)
        assert invoice["remainingMinor"] == 10_000_000
        document = await open_return(client, owner, ids, invoice)
        await scan_back(client, owner.auth, document, IMEIS[0])

        confirmed = await client.post(
            f"{API}/customer-returns/{document['id']}/confirm",
            headers=owner.auth,
            json={"debtRelief": "10000000"},
        )

        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["data"]["debtReliefMinor"] == 10_000_000
        read = await client.get(f"{API}/invoices/{invoice['id']}", headers=owner.auth)
        assert read.json()["data"]["relievedMinor"] == 10_000_000
        assert read.json()["data"]["remainingMinor"] == 0

    async def test_the_customer_drops_off_the_debtor_list(self, client, store):
        owner, ids = store
        invoice = await sell(client, owner, ids, terms=self.CREDIT_TERMS)
        document = await open_return(client, owner, ids, invoice)
        await scan_back(client, owner.auth, document, IMEIS[0])
        await client.post(
            f"{API}/customer-returns/{document['id']}/confirm",
            headers=owner.auth,
            json={"debtRelief": "10000000"},
        )

        debtors = await client.get(f"{API}/reports/debtors", headers=owner.auth)

        assert debtors.status_code == 200, debtors.text
        assert debtors.json()["data"] == []

    async def test_relief_above_the_balance_is_refused(self, client, store):
        owner, ids = store
        invoice = await sell(client, owner, ids, terms=self.CREDIT_TERMS)
        document = await open_return(client, owner, ids, invoice)
        await scan_back(client, owner.auth, document, IMEIS[0])

        refused = await client.post(
            f"{API}/customer-returns/{document['id']}/confirm",
            headers=owner.auth,
            json={"debtRelief": "11000000"},
        )

        assert refused.status_code == 409, refused.text

    async def test_a_payment_past_the_relieved_balance_is_refused(self, client, store):
        owner, ids = store
        invoice = await sell(client, owner, ids, terms=self.CREDIT_TERMS)
        document = await open_return(client, owner, ids, invoice)
        await scan_back(client, owner.auth, document, IMEIS[0])
        await client.post(
            f"{API}/customer-returns/{document['id']}/confirm",
            headers=owner.auth,
            json={"debtRelief": "10000000"},
        )

        refused = await client.post(
            f"{API}/invoices/{invoice['id']}/payments",
            headers=owner.auth,
            json={"amount": "1000"},
        )

        assert refused.status_code == 409, refused.text


class TestCancellingAReturn:
    async def test_the_handset_is_sold_again_and_the_ledgers_net_out(
        self, client, settings, store
    ):
        owner, ids = store
        invoice = await sell(client, owner, ids)
        unit = await unit_by_imei(client, owner.auth, IMEIS[0])
        document = await open_return(client, owner, ids, invoice)
        await scan_back(client, owner.auth, document, IMEIS[0])
        await client.post(
            f"{API}/customer-returns/{document['id']}/confirm",
            headers=owner.auth,
            json={},
        )

        cancelled = await client.post(
            f"{API}/customer-returns/{document['id']}/cancel",
            headers=owner.auth,
            json={"reason": "wrong phone brought in"},
        )

        assert cancelled.status_code == 200, cancelled.text
        movements, totals = await ledger_rows(settings, owner, unit["id"])
        assert [m.quantity_delta for m in movements] == [1, -1, 1, -1]
        assert totals[(TransactionType.SALES_RETURN_REFUND, Currency.USD)] == usd("0")
        assert totals[(TransactionType.SALE_REVENUE, Currency.USD)] == usd("900")
        back = await unit_by_imei(client, owner.auth, IMEIS[0])
        assert back["status"] == DeviceStatus.SOLD.value

    async def test_a_sale_with_a_standing_return_cannot_be_cancelled(
        self, client, store
    ):
        owner, ids = store
        invoice = await sell(client, owner, ids)
        document = await open_return(client, owner, ids, invoice)
        await scan_back(client, owner.auth, document, IMEIS[0])
        await client.post(
            f"{API}/customer-returns/{document['id']}/confirm",
            headers=owner.auth,
            json={},
        )

        refused = await client.post(
            f"{API}/invoices/{invoice['id']}/cancel",
            headers=owner.auth,
            json={"reason": "changed our mind"},
        )

        assert refused.status_code == 409, refused.text


class TestTakingGoodsBackIsNotASellersJob:
    """§2.1: every operation that gives value back is Owner/Manager."""

    async def test_a_seller_cannot_open_a_return(
        self, client, tenant_with_roles, create_tenant
    ):
        owner, tokens, _ = tenant_with_roles
        location = await client.post(
            f"{API}/locations", headers=owner.auth, json={"name": "Shop"}
        )
        refused = await client.post(
            f"{API}/customer-returns",
            headers=tokens["tenant.seller"],
            json={
                "salesInvoiceId": location.json()["data"]["id"],
                "locationId": location.json()["data"]["id"],
                "reason": "defective",
            },
        )

        assert refused.status_code == 403, refused.text

    async def test_a_seller_cannot_list_them(self, client, tenant_with_roles):
        _, tokens, _ = tenant_with_roles

        refused = await client.get(
            f"{API}/customer-returns",
            headers=tokens["tenant.seller"],
        )

        assert refused.status_code == 403, refused.text

    async def test_a_storekeeper_cannot_either(self, client, tenant_with_roles):
        _, tokens, _ = tenant_with_roles

        refused = await client.get(
            f"{API}/customer-returns",
            headers=tokens["tenant.storekeeper"],
        )

        assert refused.status_code == 403, refused.text


class TestBrowsingReturns:
    async def test_the_list_filters_by_reason(self, client, store):
        owner, ids = store
        invoice = await sell(client, owner, ids)
        await open_return(client, owner, ids, invoice, reason="defective")
        await open_return(client, owner, ids, invoice, reason="warranty")

        found = await client.get(
            f"{API}/customer-returns", headers=owner.auth, params={"reason": "warranty"}
        )

        assert found.status_code == 200, found.text
        rows = found.json()["data"]
        assert [row["reason"] for row in rows] == ["warranty"]
