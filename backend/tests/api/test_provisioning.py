"""PRD §3.4: provisioning creates, migrates, and seeds a real tenant database,
and every step is idempotent."""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from domain.tenancy import TenantStatus
from infrastructure import migrations
from infrastructure.config import Settings
from infrastructure.persistence.master.models import TenantDatabaseModel, TenantModel
from infrastructure.persistence.tenant.models import (
    EmployeeModel,
    LocationModel,
    TenantSettingsModel,
)
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


async def test_creating_a_tenant_drives_it_to_active(create_tenant, settings):
    tenant = await create_tenant()

    engine = create_async_engine(settings.master_db_url)
    try:
        async with AsyncSession(engine) as session:
            row = await session.get(TenantModel, UUID(tenant.tenant_id))
            assert row.status == TenantStatus.ACTIVE.value
    finally:
        await engine.dispose()


async def test_the_tenant_database_is_migrated_and_seeded(create_tenant, settings):
    tenant = await create_tenant(timezone="Europe/Berlin")
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


async def test_the_owner_is_seeded_into_the_tenant_database(create_tenant, settings):
    """PRD §3.4 step 5: the Owner is the only way into a new tenant."""
    tenant = await create_tenant(email="owner@example.com")
    url = await _tenant_url(settings, tenant.tenant_id)

    engine = create_async_engine(url)
    try:
        async with AsyncSession(engine) as session:
            rows = (
                await session.execute(
                    select(EmployeeModel.id, EmployeeModel.email, EmployeeModel.role)
                )
            ).all()
    finally:
        await engine.dispose()

    # The Employee id *is* the master user id — the ledger's FKs need that.
    assert rows == [(UUID(tenant.user_id), "owner@example.com", "tenant.owner")]


async def test_master_holds_identity_and_the_tenant_holds_presence(create_tenant, settings):
    """The split, asserted against the real schemas (PRD §3.1)."""
    await create_tenant()

    engine = create_async_engine(settings.master_db_url)
    try:
        async with engine.connect() as conn:
            tables = (
                await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                )
            ).scalars()
    finally:
        await engine.dispose()

    present = set(tables)
    # Identity is master-side; "what they may do at one store" is not.
    assert {
        "tenants",
        "tenant_databases",
        "users",
        "user_app_roles",
        "user_tenant_access",
        "invitations",
        "refresh_tokens",
    } <= present
    assert "employees" not in present
    assert "memberships" not in present


async def test_there_is_no_tenant_id_column_in_the_tenant_database(create_tenant, settings):
    """PRD §3.1: isolation is physical — a tenant_id column would mean it wasn't."""
    tenant = await create_tenant()
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


async def test_reprovisioning_is_idempotent(create_tenant, settings):
    """A FAILED tenant is retryable, so provisioning must tolerate a rerun."""
    tenant = await create_tenant()
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
            owners = (await session.scalars(select(EmployeeModel.email))).all()
            assert len(owners) == 1, "a rerun must not duplicate the Owner"
    finally:
        await engine.dispose()


async def test_each_tenant_gets_its_own_database(create_tenant, settings):
    first = await create_tenant(name="Acme Phones", slug="acme", email="a@example.com")
    second = await create_tenant(name="Beta Mobile", slug="beta", email="b@example.com")

    first_url = await _tenant_url(settings, first.tenant_id)
    second_url = await _tenant_url(settings, second.tenant_id)

    assert first_url != second_url
