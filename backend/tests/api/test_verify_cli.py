"""The three ``apexwms verify-*`` audits over a real fleet.

PRD §11 makes the ledger the source of truth and the projections
rebuildable; FR-10.7 makes goods and money reconcile per currency; §4.7
makes every customer balance a projection of invoices and payments. These
run the actual fan-out against actual databases, because a verification
routine nobody has watched find a real discrepancy is not one anyone
should trust.

**Nothing here repairs anything.** A sweep that quietly rewrote a
projection would destroy the evidence of whatever wrote it wrong.
"""

from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from infrastructure.cli import _verify
from infrastructure.persistence.master.models import TenantDatabaseModel
from tests.api.ledger_helpers import PASSWORD, PHONE_IMEI, receive_phone, tenant_url

# An IMEI no store has ever held — the surprise a count creates (FR-6.4b).
SURPRISE_IMEI = "013269009999992"


async def _execute(settings, tenant_id: str, statement: str) -> None:
    """Corrupt a projection the way a future bug would: directly."""
    engine = create_async_engine(await tenant_url(settings, tenant_id))
    try:
        async with engine.begin() as connection:
            await connection.execute(text(statement))
    finally:
        await engine.dispose()


async def _sold_on_credit(client, settings, owner) -> str:
    """A $600 phone on store credit for 7 800 000 so'm, 800 000 down."""
    from tests.api.test_credit_api import a_customer, a_scanned_invoice, confirm

    customer_id = await a_customer(client, owner)
    invoice_id = await a_scanned_invoice(client, settings, owner, customer_id=customer_id)
    await confirm(
        client,
        owner,
        invoice_id,
        paymentType="store_credit",
        debt="7800000",
        downPayment="800000",
    )
    return invoice_id

class TestACleanFleetPasses:
    async def test_a_freshly_provisioned_store_reconciles(
        self, settings, owner, capsys
    ):
        assert await _verify(settings, "verify-projections", None) == 0
        assert await _verify(settings, "verify-financials", None) == 0
        assert await _verify(settings, "verify-balances", None) == 0
        assert "everything reconciles" in capsys.readouterr().out

    async def test_a_store_with_stock_reconciles(
        self, client, settings, owner, capsys
    ):
        await receive_phone(client, settings, owner)

        assert await _verify(settings, "verify-projections", None) == 0
        assert await _verify(settings, "verify-financials", None) == 0

    async def test_a_repriced_handset_reconciles_against_its_latest_cut(
        self, client, settings, owner, capsys
    ):
        """The regression the ``latest_for_*`` reads existed to serve.

        With one log row the oldest row *is* the latest, so every other
        test here passes whichever end of the history the query returns.
        Three cuts is the smallest case that tells them apart: the unit's
        asking price is the projection of the **last** row (§4.5b), and a
        query that hands back the first reports a mismatch that is not real.
        """
        unit_id, _, _ = await receive_phone(client, settings, owner)
        for price in ("420", "390", "360"):
            resp = await client.patch(
                f"/api/v1/device-units/{unit_id}/price",
                headers=owner.auth,
                json={"askingPrice": price},
            )
            assert resp.status_code == 200, resp.text

        exit_code = await _verify(settings, "verify-projections", None)

        assert exit_code == 0, capsys.readouterr().out

    async def test_no_tenants_at_all_is_not_an_error(self, settings, capsys):
        assert await _verify(settings, "verify-projections", None) == 0
        assert "no tenant databases found" in capsys.readouterr().out


class TestDriftIsFoundAndReported:
    async def test_a_handset_moved_behind_the_ledgers_back_is_caught(
        self, client, settings, owner, capsys
    ):
        """§4.3 rule 1: there is no code path that moves a unit without a
        movement — so if one appears, this is what finds it."""
        unit_id, _, _ = await receive_phone(client, settings, owner)
        await _execute(
            settings,
            owner.tenant_id,
            f"UPDATE device_units SET location_id = NULL, status = 'sold' "
            f"WHERE id = '{unit_id}'",
        )

        exit_code = await _verify(settings, "verify-projections", None)

        out = capsys.readouterr().out
        assert exit_code == 1
        assert "MISMATCH" in out
        assert "device unit" in out

    async def test_an_asking_price_with_no_log_row_is_caught(
        self, client, settings, owner, capsys
    ):
        """§4.5b: the price is the latest row of the log, so one that
        appeared without a row has no source."""
        unit_id, _, _ = await receive_phone(client, settings, owner)
        await _execute(
            settings,
            owner.tenant_id,
            f"UPDATE device_units SET asking_price_minor = 50000 WHERE id = '{unit_id}'",
        )

        exit_code = await _verify(settings, "verify-projections", None)

        out = capsys.readouterr().out
        assert exit_code == 1
        assert "asking price" in out

    async def test_a_catalog_price_that_bypassed_its_log_is_caught(
        self, client, settings, owner, capsys
    ):
        """FR-2.19's projection, audited exactly like the unit's."""
        _, product_id, _ = await receive_phone(client, settings, owner)
        await _execute(
            settings,
            owner.tenant_id,
            f"UPDATE products SET default_sale_price_minor = 90000 "
            f"WHERE id = '{product_id}'",
        )

        exit_code = await _verify(settings, "verify-projections", None)

        assert exit_code == 1
        assert "catalog price" in capsys.readouterr().out

    async def test_goods_without_money_behind_them_are_caught(
        self, client, settings, owner, capsys
    ):
        """FR-10.7: a handset on the shelf that the money ledger never
        paid for. Surfaced as an error, never silently reconciled."""
        await receive_phone(client, settings, owner, cost="380")
        await _execute(
            settings, owner.tenant_id, "DELETE FROM financial_transactions"
        )

        exit_code = await _verify(settings, "verify-financials", None)

        out = capsys.readouterr().out
        assert exit_code == 1
        assert "inventory value in USD" in out
        assert "$380.00" in out

    async def test_a_discrepancy_is_reported_and_not_repaired(
        self, client, settings, owner
    ):
        """Run it twice: the second run reports the same thing, because
        the first one changed nothing."""
        unit_id, _, _ = await receive_phone(client, settings, owner)
        await _execute(
            settings,
            owner.tenant_id,
            f"UPDATE device_units SET asking_price_minor = 50000 WHERE id = '{unit_id}'",
        )

        assert await _verify(settings, "verify-projections", None) == 1
        assert await _verify(settings, "verify-projections", None) == 1


class TestTargetingOneStore:
    async def test_a_single_tenant_can_be_checked(
        self, client, settings, create_tenant, owner, capsys
    ):
        other = await create_tenant(
            name="Beta Mobile", slug="beta", email="b@example.com", password=PASSWORD
        )

        await _verify(settings, "verify-projections", UUID(other.tenant_id))

        out = capsys.readouterr().out
        assert "1 tenant database(s) checked" in out
        assert other.tenant_id in out
        assert owner.tenant_id not in out

    async def test_one_broken_store_does_not_hide_the_healthy_one(
        self, client, settings, create_tenant, owner, capsys
    ):
        """A fleet sweep reports everything it found, then exits non-zero —
        it does not stop at the first problem."""
        await create_tenant(
            name="Beta Mobile", slug="beta", email="b@example.com", password=PASSWORD
        )
        unit_id, _, _ = await receive_phone(client, settings, owner)
        await _execute(
            settings,
            owner.tenant_id,
            f"UPDATE device_units SET asking_price_minor = 50000 WHERE id = '{unit_id}'",
        )

        exit_code = await _verify(settings, "verify-projections", None)

        out = capsys.readouterr().out
        assert exit_code == 1
        assert "2 tenant database(s) checked" in out
        assert "ok" in out and "MISMATCH" in out

    async def test_an_unreachable_store_does_not_stop_the_run(
        self, settings, create_tenant, capsys
    ):
        await create_tenant(name="Acme Phones", slug="acme", email="a@example.com")
        broken = await create_tenant(
            name="Beta Mobile", slug="beta", email="b@example.com"
        )
        engine = create_async_engine(settings.master_db_url)
        try:
            async with AsyncSession(engine) as session:
                row = await session.get(TenantDatabaseModel, UUID(broken.tenant_id))
                row.db_name = f"apexwms_gone_{uuid4().hex[:8]}"
                await session.commit()
        finally:
            await engine.dispose()

        exit_code = await _verify(settings, "verify-financials", None)

        out = capsys.readouterr().out
        assert exit_code == 1
        assert "FAILED" in out
        assert "1 unreachable" in out


class TestDebtReconciles:
    """§4.7, FR-10.7b: a balance recomputable from immutable history is a
    balance you can trust — provided something actually recomputes it."""

    async def test_a_store_credit_sale_with_payments_reconciles(
        self, client, settings, owner, capsys
    ):
        await _sold_on_credit(client, settings, owner)

        assert await _verify(settings, "verify-balances", None) == 0

    async def test_a_payment_the_money_ledger_never_saw_is_caught(
        self, client, settings, owner, capsys
    ):
        """The bug this exists for: one of the two writes landing without
        the other, which ``PaymentPoster`` does in a single transaction and
        so can only happen if something bypasses it."""
        invoice_id = await _sold_on_credit(client, settings, owner)
        await _execute(
            settings,
            owner.tenant_id,
            "INSERT INTO payments "
            "(id, sales_invoice_id, occurred_at, amount_minor, method, user_id) "
            f"SELECT gen_random_uuid(), '{invoice_id}', now(), 500000, 'cash', "
            "created_by FROM sales_invoices "
            f"WHERE id = '{invoice_id}'",
        )

        exit_code = await _verify(settings, "verify-balances", None)

        out = capsys.readouterr().out
        assert exit_code == 1
        assert "cash collected on store credit" in out

    async def test_a_debt_edited_below_what_was_collected_is_caught(
        self, client, settings, owner, capsys
    ):
        invoice_id = await _sold_on_credit(client, settings, owner)
        await _execute(
            settings,
            owner.tenant_id,
            f"UPDATE sales_invoices SET debt_minor = 100000 WHERE id = '{invoice_id}'",
        )

        exit_code = await _verify(settings, "verify-balances", None)

        out = capsys.readouterr().out
        assert exit_code == 1
        assert "debt on INV-" in out

    async def test_nothing_is_repaired(self, client, settings, owner, capsys):
        invoice_id = await _sold_on_credit(client, settings, owner)
        await _execute(
            settings,
            owner.tenant_id,
            f"UPDATE sales_invoices SET debt_minor = 100000 WHERE id = '{invoice_id}'",
        )

        await _verify(settings, "verify-balances", None)
        capsys.readouterr()

        assert await _verify(settings, "verify-balances", None) == 1


class TestM6DocumentsReconcile:
    """The check that M6's three posters got §4.6's signs right.

    ``INVENTORY_SIGN`` reads ``WRITE_OFF_LOSS``, ``SUPPLIER_RETURN_CREDIT``
    and ``COUNT_ADJUSTMENT`` as inventory value, and no verifier was changed
    for M6. So if a poster booked a loss where a credit belonged, or a
    surplus with the wrong sign, on-hand value and the money ledger would
    disagree and this is where it shows up.
    """

    async def test_a_written_off_handset_reconciles(self, client, settings, owner):
        location_id = str((await receive_phone(client, settings, owner))[2])
        document = await client.post(
            "/api/v1/write-offs",
            headers=owner.auth,
            json={"locationId": location_id, "reason": "damage"},
        )
        assert document.status_code == 201, document.text
        document_id = document.json()["data"]["id"]
        scanned = await client.post(
            f"/api/v1/write-offs/{document_id}/scan",
            headers=owner.auth,
            json={"code": PHONE_IMEI},
        )
        assert scanned.status_code == 200, scanned.text
        confirmed = await client.post(
            f"/api/v1/write-offs/{document_id}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text

        assert await _verify(settings, "verify-projections", None) == 0
        assert await _verify(settings, "verify-financials", None) == 0

    async def test_a_returned_handset_reconciles(self, client, settings, owner):
        location_id = str((await receive_phone(client, settings, owner))[2])
        supplier = await client.post(
            "/api/v1/suppliers", headers=owner.auth, json={"name": "Tashkent Mobile"}
        )
        assert supplier.status_code == 201, supplier.text
        document = await client.post(
            "/api/v1/supplier-returns",
            headers=owner.auth,
            json={
                "supplierId": supplier.json()["data"]["id"],
                "locationId": location_id,
                "reason": "defective",
            },
        )
        assert document.status_code == 201, document.text
        document_id = document.json()["data"]["id"]
        await client.post(
            f"/api/v1/supplier-returns/{document_id}/scan",
            headers=owner.auth,
            json={"code": PHONE_IMEI},
        )
        confirmed = await client.post(
            f"/api/v1/supplier-returns/{document_id}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text

        assert await _verify(settings, "verify-projections", None) == 0
        assert await _verify(settings, "verify-financials", None) == 0

    async def test_a_count_that_wrote_a_handset_off_reconciles(
        self, client, settings, owner
    ):
        """The M6 demo, checked from the ledger's side: the shortage is
        booked at book value, so nothing drifts."""
        location_id = str((await receive_phone(client, settings, owner))[2])
        count = await client.post(
            "/api/v1/stock-counts", headers=owner.auth, json={"locationId": location_id}
        )
        assert count.status_code == 201, count.text
        count_id = count.json()["data"]["id"]
        # Scan nothing: the handset is missing.
        await client.post(f"/api/v1/stock-counts/{count_id}/close", headers=owner.auth, json={})
        confirmed = await client.post(
            f"/api/v1/stock-counts/{count_id}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text

        assert await _verify(settings, "verify-projections", None) == 0
        assert await _verify(settings, "verify-financials", None) == 0

    async def test_a_count_that_found_a_surprise_reconciles(
        self, client, settings, owner
    ):
        """The surplus side, which is the one that has to create a unit and
        book its value in the same transaction."""
        _, product, location = await receive_phone(client, settings, owner)
        product_id, location_id = str(product), str(location)
        count = await client.post(
            "/api/v1/stock-counts", headers=owner.auth, json={"locationId": location_id}
        )
        count_id = count.json()["data"]["id"]
        await client.post(
            f"/api/v1/stock-counts/{count_id}/scan",
            headers=owner.auth,
            json={"code": PHONE_IMEI},
        )
        surprise = await client.post(
            f"/api/v1/stock-counts/{count_id}/scan",
            headers=owner.auth,
            json={
                "code": SURPRISE_IMEI,
                "productId": product_id,
                "acquisitionCost": "300.00",
            },
        )
        assert surprise.status_code == 200, surprise.text
        await client.post(f"/api/v1/stock-counts/{count_id}/close", headers=owner.auth, json={})
        confirmed = await client.post(
            f"/api/v1/stock-counts/{count_id}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text

        assert await _verify(settings, "verify-projections", None) == 0
        assert await _verify(settings, "verify-financials", None) == 0

    async def test_a_cancelled_write_off_still_reconciles(self, client, settings, owner):
        """Compensation nets to zero on both sides, or it nets to zero on
        neither (§4.3 rule 2)."""
        location_id = str((await receive_phone(client, settings, owner))[2])
        document = await client.post(
            "/api/v1/write-offs",
            headers=owner.auth,
            json={"locationId": location_id, "reason": "loss"},
        )
        document_id = document.json()["data"]["id"]
        await client.post(
            f"/api/v1/write-offs/{document_id}/scan",
            headers=owner.auth,
            json={"code": PHONE_IMEI},
        )
        await client.post(
            f"/api/v1/write-offs/{document_id}/confirm", headers=owner.auth, json={}
        )
        cancelled = await client.post(
            f"/api/v1/write-offs/{document_id}/cancel", headers=owner.auth, json={}
        )
        assert cancelled.status_code == 200, cancelled.text

        assert await _verify(settings, "verify-projections", None) == 0
        assert await _verify(settings, "verify-financials", None) == 0

    async def test_a_handset_counted_at_another_location_reconciles(
        self, client, settings, owner, capsys
    ):
        """The regression this test exists for.

        A handset the books already hold, found on a different shelf, is a
        *location* correction — the store owns it and already booked what it
        paid. Booking its cost a second time reports inventory worth double
        the shelves, and nothing but this reconciliation would show it.
        """
        await receive_phone(client, settings, owner)
        second = await client.post(
            "/api/v1/locations", headers=owner.auth, json={"name": "Stockroom"}
        )
        assert second.status_code == 201, second.text

        count = await client.post(
            "/api/v1/stock-counts",
            headers=owner.auth,
            json={"locationId": second.json()["data"]["id"]},
        )
        count_id = count.json()["data"]["id"]
        found = await client.post(
            f"/api/v1/stock-counts/{count_id}/scan",
            headers=owner.auth,
            json={"code": PHONE_IMEI},
        )
        assert found.status_code == 200, found.text
        assert found.json()["data"]["unit"]["outcome"] == "unexpected"
        await client.post(f"/api/v1/stock-counts/{count_id}/close", headers=owner.auth, json={})
        confirmed = await client.post(
            f"/api/v1/stock-counts/{count_id}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text

        assert await _verify(settings, "verify-projections", None) == 0
        assert await _verify(settings, "verify-financials", None) == 0, (
            capsys.readouterr().out
        )

    async def test_a_handset_sold_while_the_count_was_open_reconciles(
        self, client, settings, owner, capsys
    ):
        """The mirror regression.

        The snapshot froze what the books said when the count opened. A
        phone sold since is not missing, it is sold — the ledger already
        accounts for it, and writing it off again takes its cost out twice
        and leaves inventory value negative.
        """
        unit_id, _, location_id = await receive_phone(client, settings, owner)
        priced = await client.patch(
            f"/api/v1/device-units/{unit_id}/price",
            headers=owner.auth,
            json={"askingPrice": "420"},
        )
        assert priced.status_code == 200, priced.text

        count = await client.post(
            "/api/v1/stock-counts",
            headers=owner.auth,
            json={"locationId": str(location_id)},
        )
        count_id = count.json()["data"]["id"]

        invoice = await client.post(
            "/api/v1/invoices",
            headers=owner.auth,
            json={"locationId": str(location_id)},
        )
        invoice_id = invoice.json()["data"]["id"]
        await client.post(
            f"/api/v1/invoices/{invoice_id}/scan",
            headers=owner.auth,
            json={"code": PHONE_IMEI},
        )
        sold = await client.post(
            f"/api/v1/invoices/{invoice_id}/confirm",
            headers=owner.auth,
            json={"paymentType": "paid_in_full"},
        )
        assert sold.status_code == 200, sold.text

        await client.post(f"/api/v1/stock-counts/{count_id}/close", headers=owner.auth, json={})
        confirmed = await client.post(
            f"/api/v1/stock-counts/{count_id}/confirm", headers=owner.auth, json={}
        )
        assert confirmed.status_code == 200, confirmed.text

        assert await _verify(settings, "verify-projections", None) == 0
        assert await _verify(settings, "verify-financials", None) == 0, (
            capsys.readouterr().out
        )
