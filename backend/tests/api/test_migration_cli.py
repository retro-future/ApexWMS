"""PRD §3.2: the migration fan-out is idempotent, resumable, and reports
the fleet's version spread rather than crashing on a partial run."""

from uuid import UUID, uuid4

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
    # Read from the scripts, not written down: the assertion is "both are at
    # head", which must keep holding when the next revision lands.
    assert f"{migrations.head_revision('tenant')}: 2" in out


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
    # A unique name, and dropped afterwards: the test server outlives the run.
    db_name = f"{settings.tenant_db_name_prefix}probe_{uuid4().hex[:8]}"
    engine = create_async_engine(settings.master_db_url)
    try:
        async with engine.connect() as conn:
            autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await autocommit.execute(text(f'CREATE DATABASE "{db_name}"'))

        url = tenant_db_url(settings.master_db_url, db_name)
        assert await migrations.current_revision(url) is None

        await migrations.upgrade("tenant", url)
        assert await migrations.current_revision(url) == migrations.head_revision("tenant")
    finally:
        async with engine.connect() as conn:
            autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
            await autocommit.execute(text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
        await engine.dispose()
