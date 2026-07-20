"""Integration-test fixtures: a real Postgres, a migrated MasterDB, an ASGI client.

Tests that need a database ask for the ``client`` (or ``settings``)
fixture. When Docker is unavailable the whole set skips rather than
fails, so the unit suites still run on any machine (PRD §9 Testing).
"""

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
import pytest_asyncio

from infrastructure import migrations
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
                    "TRUNCATE invitations, refresh_tokens, memberships, "
                    "tenant_databases, users, tenants CASCADE"
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
    """A signed-up tenant and the credentials to act as its Owner."""

    def __init__(self, client: httpx.AsyncClient, body: dict, email: str, password: str) -> None:
        self._client = client
        self.tenant_id = body["tenant_id"]
        self.access_token = body["access_token"]
        self.refresh_token = body["refresh_token"]
        self.email = email
        self.password = password

    @property
    def auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}


@pytest.fixture
def sign_up(client: httpx.AsyncClient):
    """Signs up a tenant; provisioning runs inline, so it returns ready to use."""

    async def _sign_up(
        name: str = "Acme Phones",
        email: str = "owner@example.com",
        password: str = "hunter2000",
        timezone: str = "Asia/Tashkent",
    ) -> Tenant:
        resp = await client.post(
            "/api/v1/auth/signup",
            json={
                "tenant_name": name,
                "email": email,
                "password": password,
                "full_name": "Test Owner",
                "timezone": timezone,
            },
        )
        assert resp.status_code == 201, resp.text
        return Tenant(client, resp.json(), email, password)

    return _sign_up
