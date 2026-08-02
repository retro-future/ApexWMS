"""``apexwms verify-projections`` / ``verify-financials`` over a real fleet.

PRD §11 makes the ledger the source of truth and the projections
rebuildable; FR-10.7 makes goods and money reconcile per currency. These
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
from tests.api.ledger_helpers import PASSWORD, receive_phone, tenant_url


async def _execute(settings, tenant_id: str, statement: str) -> None:
    """Corrupt a projection the way a future bug would: directly."""
    engine = create_async_engine(await tenant_url(settings, tenant_id))
    try:
        async with engine.begin() as connection:
            await connection.execute(text(statement))
    finally:
        await engine.dispose()


class TestACleanFleetPasses:
    async def test_a_freshly_provisioned_store_reconciles(
        self, settings, owner, capsys
    ):
        assert await _verify(settings, "verify-projections", None) == 0
        assert await _verify(settings, "verify-financials", None) == 0
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
