"""Container wiring tests — resolution only, no database connection.

SQLAlchemy engines are lazy: creating one never touches the network, so
these tests prove the DI graph is sound without needing Postgres. The
tenant path itself is exercised end to end in tests/api/.
"""

import pytest
from dishka import Scope
from dishka.exceptions import NoContextValueError

from application.dtos import CurrentUser
from application.ports import Clock, PasswordHasher, TokenService
from di import create_container
from infrastructure.config import Settings
from infrastructure.tenancy import TenantContext, TenantEngineRegistry
from infrastructure.types import MasterEngine, MasterSession

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


async def test_security_services_are_app_scoped():
    container = create_container(Settings(master_db_url=TEST_URL))
    try:
        hasher = await container.get(PasswordHasher)
        assert await container.get(PasswordHasher) is hasher
        assert await container.get(TokenService) is await container.get(TokenService)
        assert await container.get(Clock) is not None
    finally:
        await container.close()


async def test_request_scope_provides_the_master_session():
    container = create_container(Settings(master_db_url=TEST_URL))
    try:
        async with container(scope=Scope.REQUEST) as request:
            session = await request.get(MasterSession)
            assert session.bind.url.database == "apexwms_master_test"
    finally:
        await container.close()


async def test_the_tenant_context_is_no_longer_supplied_from_outside():
    """It is derived from the validated JWT plus MasterDB (PRD §3.3), so
    resolving it without an authenticated request must fail rather than
    silently accept an injected tenant."""
    container = create_container(Settings(master_db_url=TEST_URL))
    try:
        async with container(scope=Scope.REQUEST) as request:
            with pytest.raises(NoContextValueError):
                await request.get(TenantContext)
    finally:
        await container.close()


async def test_current_user_requires_a_request():
    container = create_container(Settings(master_db_url=TEST_URL))
    try:
        async with container(scope=Scope.REQUEST) as request:
            with pytest.raises(NoContextValueError):
                await request.get(CurrentUser)
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
