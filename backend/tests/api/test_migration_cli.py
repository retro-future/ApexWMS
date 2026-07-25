"""PRD §3.2: the migration fan-out is idempotent, resumable, and reports
the fleet's version spread rather than crashing on a partial run."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from infrastructure import migrations
from infrastructure.cli import _migrate_tenants
from infrastructure.persistence.master.models import TenantDatabaseModel
from infrastructure.tenancy import tenant_db_url


async def test_fan_out_reports_every_tenant_at_head(create_tenant, settings, capsys):
    await create_tenant(name="Acme Phones", slug="acme", email="a@example.com")
    await create_tenant(name="Beta Mobile", slug="beta", email="b@example.com")

    exit_code = await _migrate_tenants(settings, tenant_id=None)

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "2 tenant database(s)" in out
    assert "0001_tenant: 2" in out


async def test_fan_out_is_idempotent(create_tenant, settings):
    await create_tenant()

    assert await _migrate_tenants(settings, tenant_id=None) == 0
    assert await _migrate_tenants(settings, tenant_id=None) == 0


async def test_fan_out_with_no_tenants_is_not_an_error(settings, capsys):
    exit_code = await _migrate_tenants(settings, tenant_id=None)

    assert exit_code == 0
    assert "no tenant databases found" in capsys.readouterr().out


async def test_a_single_tenant_can_be_targeted(create_tenant, settings, capsys):
    first = await create_tenant(name="Acme Phones", slug="acme", email="a@example.com")
    await create_tenant(name="Beta Mobile", slug="beta", email="b@example.com")

    await _migrate_tenants(settings, tenant_id=UUID(first.tenant_id))

    out = capsys.readouterr().out
    assert "1 tenant database(s)" in out
    assert first.tenant_id in out


async def test_an_unreachable_tenant_is_reported_without_stopping_the_run(
    create_tenant, settings, capsys
):
    """A partially-migrated fleet is an expected state, not an emergency."""
    healthy = await create_tenant(name="Acme Phones", slug="acme", email="a@example.com")
    broken = await create_tenant(name="Beta Mobile", slug="beta", email="b@example.com")

    # Point one tenant at a database that does not exist.
    engine = create_async_engine(settings.master_db_url)
    try:
        async with AsyncSession(engine) as session:
            row = await session.get(TenantDatabaseModel, UUID(broken.tenant_id))
            row.db_name = "apexwms_tenant_does_not_exist"
            await session.commit()
    finally:
        await engine.dispose()

    exit_code = await _migrate_tenants(settings, tenant_id=None)

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "FAILED" in out
    assert "1 failure(s)" in out
    # The healthy tenant was still migrated.
    assert f"ok      {healthy.tenant_id}" in out


async def test_current_revision_is_none_before_migration(settings):
    """The version probe tolerates a database with no alembic_version table."""
    engine = create_async_engine(settings.master_db_url)
    try:
        async with engine.connect() as conn:
            autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await autocommit.execute(text('CREATE DATABASE "apexwms_probe_test"'))
    finally:
        await engine.dispose()

    url = tenant_db_url(settings.master_db_url, "apexwms_probe_test")
    assert await migrations.current_revision(url) is None

    await migrations.upgrade("tenant", url)
    assert await migrations.current_revision(url) == "0001_tenant"
