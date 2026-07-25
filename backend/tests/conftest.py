"""Integration-test fixtures: a real Postgres, a migrated MasterDB, an ASGI client.

Tests that need a database ask for the ``client`` (or ``settings``)
fixture. When Docker is unavailable the whole set skips rather than
fails, so the unit suites still run on any machine (PRD §9 Testing).
"""

from collections.abc import AsyncIterator, Iterator
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio

from application.dtos import CreateTenantCommand
from application.use_cases import CreateSuperAdmin, CreateTenant
from infrastructure import migrations
from infrastructure.clock import SystemClock
from infrastructure.config import Settings
from presentation.app import create_app


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    """A throwaway Postgres 16, matching docker-compose.yml's image."""
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:  # pragma: no cover - dev dependency is declared
        pytest.skip("testcontainers is not installed")

    try:
        container = PostgresContainer("postgres:16-alpine", driver="asyncpg")
        container.start()
    except Exception as exc:  # noqa: BLE001 - any docker failure means "skip"
        pytest.skip(f"Docker is not available for integration tests: {exc}")

    try:
        yield container.get_connection_url()
    finally:
        container.stop()


@pytest.fixture(scope="session")
def migrated_master(postgres_url: str) -> str:
    migrations.upgrade_sync("master", postgres_url)
    return postgres_url


@pytest_asyncio.fixture(autouse=True)
async def clean_master(request) -> AsyncIterator[None]:
    """Each test starts with an empty MasterDB.

    Tenant databases from previous tests are left behind — they are
    unreachable without their (now-deleted) tenant row, and the whole
    container is thrown away at the end of the session.
    """
    yield
    if "migrated_master" not in request.fixturenames:
        return
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(request.getfixturevalue("migrated_master"))
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE refresh_tokens, invitations, user_tenant_access, "
                    "user_app_roles, users, tenant_databases, tenants CASCADE"
                )
            )
    finally:
        await engine.dispose()


@pytest.fixture
def settings(migrated_master: str) -> Settings:
    return Settings(
        master_db_url=migrated_master,
        # At least 32 bytes, or PyJWT warns about HMAC key length (RFC 7518).
        jwt_secret="integration-test-secret-key-of-sufficient-length",
        # Keep the registry small so eviction is exercised by ordinary runs.
        max_live_tenant_engines=5,
        tenant_pool_size=1,
    )


@pytest_asyncio.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        yield client


class Tenant:
    """A provisioned store and the credentials to act as its Owner."""

    def __init__(
        self,
        tenant_id: str,
        slug: str,
        email: str,
        password: str,
        user_id: str,
        access_token: str,
        refresh_token: str,
    ) -> None:
        self.tenant_id = tenant_id
        self.slug = slug
        self.email = email
        self.password = password
        self.user_id = user_id
        self.access_token = access_token
        self.refresh_token = refresh_token

    @property
    def auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    @property
    def header(self) -> dict[str, str]:
        """``X-Tenant`` naming this store — only needed to switch into it."""
        return {"X-Tenant": self.slug}


def _master_session(settings: Settings):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(settings.master_db_url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _token_service(settings: Settings, clock):
    from infrastructure.security.tokens import JwtTokenService

    return JwtTokenService(
        settings.jwt_secret, timedelta(minutes=settings.access_token_ttl_minutes), clock
    )


@pytest.fixture
def create_tenant(client: httpx.AsyncClient, settings: Settings):
    """Provisions a store the way a SuperAdmin would, then logs its Owner in.

    There is no sign-up endpoint (PRD §3.4), so this drives the same
    ``CreateTenant`` use case the ``apexwms create-tenant`` CLI does.
    """
    from infrastructure.persistence.master.repositories import (
        SqlTenantRepository,
        SqlUserRepository,
    )
    from infrastructure.persistence.master.uow import SqlMasterUnitOfWork
    from infrastructure.provisioning import DefaultTenantProvisioner
    from infrastructure.security.password import Argon2PasswordHasher

    async def _create(
        name: str = "Acme Phones",
        slug: str = "acme",
        email: str = "owner@example.com",
        timezone: str = "Asia/Tashkent",
        password: str | None = None,
    ) -> Tenant:
        engine, sessions = _master_session(settings)
        try:
            async with sessions() as session:
                clock = SystemClock()
                result = await CreateTenant(
                    tenants=SqlTenantRepository(session),
                    users=SqlUserRepository(session),
                    hasher=Argon2PasswordHasher(),
                    tokens=_token_service(settings, clock),
                    provisioner=DefaultTenantProvisioner(engine, settings),
                    clock=clock,
                    uow=SqlMasterUnitOfWork(session),
                ).execute(
                    CreateTenantCommand(
                        name=name,
                        slug=slug,
                        owner_email=email,
                        owner_full_name="Test Owner",
                        timezone=timezone,
                    )
                )
        finally:
            await engine.dispose()

        # Login needs no tenant header: the claim is stamped from users.tenant_id.
        temp = result.temporary_password
        resp = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": temp}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        tenant = Tenant(
            tenant_id=str(result.tenant_id),
            slug=slug,
            email=email,
            password=temp,
            user_id=str(result.owner_user_id),
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
        )

        # Most tests want a settled Owner, not one mid-onboarding. Tests that
        # care about the temporary-password flow pass no explicit password.
        if password is not None:
            resp = await client.post(
                "/api/v1/auth/change-password",
                json={"current_password": temp, "new_password": password},
                headers=tenant.auth,
            )
            assert resp.status_code == 204, resp.text
            resp = await client.post(
                "/api/v1/auth/login", json={"email": email, "password": password}
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            tenant.password = password
            tenant.access_token = body["access_token"]
            tenant.refresh_token = body["refresh_token"]

        return tenant

    return _create


@pytest.fixture
def create_superadmin(settings: Settings):
    """A platform operator: no home store, so their token carries no tenant."""
    from infrastructure.persistence.master.repositories import (
        SqlUserAppRoleRepository,
        SqlUserRepository,
    )
    from infrastructure.persistence.master.uow import SqlMasterUnitOfWork
    from infrastructure.security.password import Argon2PasswordHasher

    async def _create(email: str = "ops@example.com", name: str = "Ops") -> tuple[str, str]:
        engine, sessions = _master_session(settings)
        try:
            async with sessions() as session:
                clock = SystemClock()
                user, password = await CreateSuperAdmin(
                    users=SqlUserRepository(session),
                    app_roles=SqlUserAppRoleRepository(session),
                    hasher=Argon2PasswordHasher(),
                    tokens=_token_service(settings, clock),
                    clock=clock,
                    uow=SqlMasterUnitOfWork(session),
                ).execute(email, name)
        finally:
            await engine.dispose()
        return email, password

    return _create


@pytest.fixture
def grant_access(settings: Settings):
    """Give a user access to a second store — the multi-store switching case."""
    from uuid import UUID

    from domain.entities import UserTenantAccess
    from infrastructure.persistence.master.repositories import (
        SqlUserTenantAccessRepository,
    )
    from infrastructure.persistence.master.uow import SqlMasterUnitOfWork

    async def _grant(user_id: str, tenant_id: str) -> None:
        from uuid import uuid4

        engine, sessions = _master_session(settings)
        try:
            async with sessions() as session:
                await SqlUserTenantAccessRepository(session).add(
                    UserTenantAccess(
                        id=uuid4(), user_id=UUID(user_id), tenant_id=UUID(tenant_id)
                    )
                )
                await SqlMasterUnitOfWork(session).commit()
        finally:
            await engine.dispose()

    return _grant
