"""Container wiring tests — resolution only, no database connection.

SQLAlchemy engines are lazy: creating one never touches the network, so
these tests prove the DI graph is sound without needing Postgres.
"""

from dishka import Scope

from di import create_container
from infrastructure.config import Settings
from infrastructure.tenancy import TenantContext, TenantEngineRegistry
from infrastructure.types import MasterEngine, MasterSession, TenantSession

TEST_URL = "postgresql+asyncpg://user:pass@localhost:5432/apexwms_master_test"


async def test_settings_come_from_context():
    settings = Settings(master_db_url=TEST_URL)
    container = create_container(settings)
    try:
        assert await container.get(Settings) is settings
    finally:
        await container.close()


async def test_master_engine_is_app_scoped_and_uses_settings_url():
    container = create_container(Settings(master_db_url=TEST_URL))
    try:
        engine = await container.get(MasterEngine)
        assert engine.url.database == "apexwms_master_test"
        assert await container.get(MasterEngine) is engine
    finally:
        await container.close()


async def test_request_scope_provides_master_and_tenant_sessions():
    container = create_container(Settings(master_db_url=TEST_URL))
    tenant = TenantContext(
        tenant_id="t1",
        db_url="postgresql+asyncpg://user:pass@localhost:5432/apexwms_tenant_t1",
    )
    try:
        async with container(context={TenantContext: tenant}, scope=Scope.REQUEST) as request:
            master_session = await request.get(MasterSession)
            tenant_session = await request.get(TenantSession)
            assert master_session.bind.url.database == "apexwms_master_test"
            assert tenant_session.bind.url.database == "apexwms_tenant_t1"
    finally:
        await container.close()


async def test_tenant_engines_are_cached_in_the_registry():
    container = create_container(Settings(master_db_url=TEST_URL))
    tenant = TenantContext(
        tenant_id="t1",
        db_url="postgresql+asyncpg://user:pass@localhost:5432/apexwms_tenant_t1",
    )
    try:
        registry = await container.get(TenantEngineRegistry)
        assert await registry.get(tenant) is await registry.get(tenant)
    finally:
        await container.close()
