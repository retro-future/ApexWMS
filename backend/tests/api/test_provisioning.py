"""PRD §3.4: provisioning creates, migrates, and seeds a real tenant database,
and every step is idempotent."""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from domain.tenancy import TenantStatus
from infrastructure import migrations
from infrastructure.config import Settings
from infrastructure.persistence.master.models import TenantDatabaseModel, TenantModel
from infrastructure.persistence.tenant.models import LocationModel, TenantSettingsModel
from infrastructure.provisioning import DEFAULT_LOCATION_NAME, DefaultTenantProvisioner
from infrastructure.tenancy import tenant_db_url


async def _tenant_url(settings: Settings, tenant_id: str) -> str:
    engine = create_async_engine(settings.master_db_url)
    try:
        async with AsyncSession(engine) as session:
            row = await session.get(TenantDatabaseModel, UUID(tenant_id))
            assert row is not None, "provisioning recorded no tenant_databases row"
            return tenant_db_url(settings.master_db_url, row.db_name)
    finally:
        await engine.dispose()


async def test_signup_drives_the_tenant_to_active(sign_up, settings):
    tenant = await sign_up()

    engine = create_async_engine(settings.master_db_url)
    try:
        async with AsyncSession(engine) as session:
            row = await session.get(TenantModel, UUID(tenant.tenant_id))
            assert row.status == TenantStatus.ACTIVE.value
    finally:
        await engine.dispose()


async def test_the_tenant_database_is_migrated_and_seeded(sign_up, settings):
    tenant = await sign_up(timezone="Europe/Berlin")
    url = await _tenant_url(settings, tenant.tenant_id)

    assert await migrations.current_revision(url) == "0001_tenant"

    engine = create_async_engine(url)
    try:
        async with AsyncSession(engine) as session:
            tz = await session.scalar(select(TenantSettingsModel.timezone))
            assert tz == "Europe/Berlin"
            locations = (await session.scalars(select(LocationModel.name))).all()
            assert list(locations) == [DEFAULT_LOCATION_NAME]
    finally:
        await engine.dispose()


async def test_there_is_no_tenant_id_column_in_the_tenant_database(sign_up, settings):
    """PRD §3.1: isolation is physical — a tenant_id column would mean it wasn't."""
    tenant = await sign_up()
    url = await _tenant_url(settings, tenant.tenant_id)

    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            columns = (
                await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public'"
                    )
                )
            ).scalars()
        assert "tenant_id" not in set(columns)
    finally:
        await engine.dispose()


async def test_reprovisioning_is_idempotent(sign_up, settings):
    """A FAILED tenant is retryable, so provisioning must tolerate a rerun."""
    tenant = await sign_up()
    url = await _tenant_url(settings, tenant.tenant_id)

    master = create_async_engine(settings.master_db_url)
    try:
        await DefaultTenantProvisioner(master, settings).provision(
            UUID(tenant.tenant_id), "Asia/Tashkent"
        )
        async with AsyncSession(master) as session:
            row = await session.get(TenantModel, UUID(tenant.tenant_id))
            assert row.status == TenantStatus.ACTIVE.value
    finally:
        await master.dispose()

    engine = create_async_engine(url)
    try:
        async with AsyncSession(engine) as session:
            locations = (await session.scalars(select(LocationModel.name))).all()
            # The seed did not run twice.
            assert list(locations) == [DEFAULT_LOCATION_NAME]
    finally:
        await engine.dispose()


async def test_each_tenant_gets_its_own_database(sign_up, settings):
    first = await sign_up(name="Acme Phones", email="a@example.com")
    second = await sign_up(name="Beta Mobile", email="b@example.com")

    first_url = await _tenant_url(settings, first.tenant_id)
    second_url = await _tenant_url(settings, second.tenant_id)

    assert first_url != second_url
