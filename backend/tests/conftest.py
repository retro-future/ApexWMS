"""Integration-test fixtures: a real Postgres, a migrated MasterDB, an ASGI client.

Tests that need a database ask for the ``client`` (or ``settings``)
fixture. When Docker is unavailable the whole set skips rather than
fails, so the unit suites still run on any machine (PRD §9 Testing).

Every database this session owns is named ``apexwms_test_*`` and suffixed
with the xdist worker id, so parallel workers never share a MasterDB and
``clean_master`` cannot truncate another worker's rows.
"""

import contextlib
import os
import time
from collections.abc import AsyncIterator, Iterator
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from application.commands.create_superadmin import (
    CreateSuperAdminCommand,
    CreateSuperAdminHandler,
)
from application.commands.create_tenant import CreateTenantCommand, CreateTenantHandler
from application.services import SlugNormalizer, TimezoneValidator
from infrastructure import migrations
from infrastructure.clock import SystemClock
from infrastructure.config import Settings
from presentation.app import create_app

TEST_DB_PREFIX = "apexwms_test_"

# Set by the ``tenant_template`` fixture. A module global rather than a fixture
# lookup because the patched provisioner reads it from inside a running loop.
_TEMPLATE_DB: str | None = None


@event.listens_for(Engine, "do_connect")
def _retry_dropped_connections(dialect, conn_rec, cargs, cparams):
    """Retry a connect that Windows tore down before it completed.

    Docker Desktop's localhost port proxy drops the occasional socket once
    several xdist workers are connecting at the same time (WinError 64). The
    server is fine, so a short retry is enough. Test-only: registered here,
    never in ``src``.
    """
    for delay in (0.05, 0.15, 0.4, None):
        try:
            return dialect.connect(*cargs, **cparams)
        except OSError:
            if delay is None:
                raise
            time.sleep(delay)


def _run_autocommit(admin_url: str, statements: list[str], tolerate_failure: bool = False) -> None:
    """CREATE/DROP DATABASE cannot run inside a transaction."""
    import asyncio

    async def go() -> None:
        engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as conn:
                for statement in statements:
                    if tolerate_failure:
                        with contextlib.suppress(Exception):
                            await conn.execute(text(statement))
                    else:
                        await conn.execute(text(statement))
        finally:
            await engine.dispose()

    asyncio.run(go())


def _list_test_databases(admin_url: str, pattern: str) -> list[str]:
    import asyncio

    async def go() -> list[str]:
        engine = create_async_engine(admin_url)
        try:
            async with engine.connect() as conn:
                rows = await conn.execute(
                    text("SELECT datname FROM pg_database WHERE datname LIKE :p"),
                    {"p": pattern},
                )
                return [row[0] for row in rows]
        finally:
            await engine.dispose()

    return asyncio.run(go())


@pytest.fixture(scope="session")
def postgres_url(worker_id: str) -> Iterator[str]:
    """An admin connection URL for a Postgres 16 the session may create databases in.

    Prefers the docker-compose server, because a testcontainer cannot be
    shared between xdist workers.
    """
    compose_url = os.environ.get("APEXWMS_TEST_DB_URL") or Settings().master_db_url
    try:
        _run_autocommit(compose_url, ["SELECT 1"])
    except Exception:  # noqa: BLE001 - unreachable means "fall back"
        pass
    else:
        yield compose_url
        return

    if worker_id != "master":
        pytest.skip(
            "parallel runs need a shared Postgres — start it with `docker compose up -d`"
        )

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
def migrated_master(postgres_url: str, worker_id: str) -> Iterator[str]:
    """This worker's own MasterDB, dropped and recreated so reruns are clean."""
    name = f"{TEST_DB_PREFIX}master_{worker_id}"
    url = make_url(postgres_url).set(database=name).render_as_string(hide_password=False)
    _run_autocommit(
        postgres_url,
        [f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', f'CREATE DATABASE "{name}"'],
    )
    migrations.upgrade_sync("master", url)

    yield url

    leftovers = _list_test_databases(postgres_url, f"{TEST_DB_PREFIX}%{worker_id}%")
    leftovers += _list_test_databases(postgres_url, f"{TEST_DB_PREFIX}{worker_id}_%")
    _run_autocommit(
        postgres_url,
        [f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)' for db in dict.fromkeys(leftovers)],
        tolerate_failure=True,
    )


@pytest_asyncio.fixture
async def master_engine(migrated_master: str) -> AsyncIterator[AsyncEngine]:
    """One MasterDB engine per test, shared by every fixture below.

    Not session-scoped: each test runs in its own event loop and an asyncpg
    pool cannot outlive the loop that opened its connections.
    """
    engine = create_async_engine(migrated_master)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def tenant_template(postgres_url: str, worker_id: str, migrated_master: str) -> str:
    """A migrated but unseeded tenant database, copied per provision.

    Running the 12 tenant migrations costs ~1.6 s; copying this template
    costs ~0.09 s, and the copy carries ``alembic_version`` at head so the
    provisioner's own ``upgrade`` call stays real and returns immediately.
    """
    global _TEMPLATE_DB
    name = f"{TEST_DB_PREFIX}tpl_{worker_id}"
    url = make_url(postgres_url).set(database=name).render_as_string(hide_password=False)
    _run_autocommit(
        postgres_url,
        [f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', f'CREATE DATABASE "{name}"'],
    )
    migrations.upgrade_sync("tenant", url)
    _TEMPLATE_DB = name
    return name


class _TemplateAwareMigrations:
    """Stands in for the ``migrations`` module inside ``provisioning`` only.

    A template copy already carries ``alembic_version`` at head, so the
    provisioner's tenant upgrade is a no-op that still opens a connection from
    a fresh thread and event loop — the churn that makes Windows drop sockets
    once workers run in parallel. Every other attribute, and every other
    module's ``migrations``, is untouched.
    """

    def __getattr__(self, name: str):
        return getattr(migrations, name)

    async def upgrade(self, kind: str, db_url: str) -> None:
        if kind != "tenant" or _TEMPLATE_DB is None:
            await migrations.upgrade(kind, db_url)


@pytest.fixture(scope="session", autouse=True)
def provision_from_template() -> Iterator[None]:
    """Make the provisioner copy the template instead of migrating from empty.

    Test-only: production provisioning still creates an empty database.
    """
    from infrastructure import provisioning
    from infrastructure.provisioning import DefaultTenantProvisioner

    async def _create_database(self, db_name: str) -> None:
        template = _TEMPLATE_DB
        clause = f' TEMPLATE "{template}"' if template else ""
        async with self._engine.connect() as conn:
            autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
            try:
                await autocommit.execute(text(f'CREATE DATABASE "{db_name}"{clause}'))
            except Exception as exc:  # noqa: BLE001 - mirrors the real duplicate check
                orig = getattr(exc, "orig", None)
                if getattr(orig, "sqlstate", None) != "42P04":
                    raise

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(DefaultTenantProvisioner, "_create_database", _create_database)
        patch.setattr(provisioning, "migrations", _TemplateAwareMigrations())
        yield


@pytest.fixture(scope="session", autouse=True)
def cheap_password_hashing() -> Iterator[None]:
    """Argon2's real cost factors add ~0.2 s per API test and prove nothing here."""
    from argon2 import PasswordHasher as _Argon2Hasher

    from infrastructure.security import password as password_module

    def __init__(self) -> None:
        self._hasher = _Argon2Hasher(time_cost=1, memory_cost=8192, parallelism=1)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(password_module.Argon2PasswordHasher, "__init__", __init__)
        yield


@pytest_asyncio.fixture(autouse=True)
async def clean_master(request) -> AsyncIterator[None]:
    """Each test starts with an empty MasterDB.

    Tenant databases from previous tests are left behind — they are
    unreachable without their (now-deleted) tenant row, and every
    ``apexwms_test_*`` database is dropped at the end of the session.
    """
    yield
    if "migrated_master" not in request.fixturenames:
        return
    # Its own engine, not the ``master_engine`` fixture: an autouse fixture is
    # torn down after the fixtures it did not declare as dependencies.
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
def settings(migrated_master: str, worker_id: str, tenant_template: str) -> Settings:
    return Settings(
        master_db_url=migrated_master,
        # At least 32 bytes, or PyJWT warns about HMAC key length (RFC 7518).
        jwt_secret="integration-test-secret-key-of-sufficient-length",
        # Keep the registry small so eviction is exercised by ordinary runs.
        max_live_tenant_engines=5,
        tenant_pool_size=1,
        # Marks every database this worker creates, so teardown can find them.
        tenant_db_name_prefix=f"{TEST_DB_PREFIX}{worker_id}_",
    )


@pytest_asyncio.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Accept-Language": "en"},
        ) as client,
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
        full_name: str,
        access_token: str,
        refresh_token: str,
    ) -> None:
        self.tenant_id = tenant_id
        self.slug = slug
        self.email = email
        self.password = password
        self.user_id = user_id
        self.full_name = full_name
        self.access_token = access_token
        self.refresh_token = refresh_token

    @property
    def auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    @property
    def header(self) -> dict[str, str]:
        """``X-Tenant`` naming this store — only needed to switch into it."""
        return {"X-Tenant": self.slug}


def _master_sessions(engine: AsyncEngine):
    from sqlalchemy.ext.asyncio import async_sessionmaker

    return async_sessionmaker(engine, expire_on_commit=False)


def _token_service(settings: Settings, clock):
    from infrastructure.security.tokens import JwtTokenService

    return JwtTokenService(
        settings.jwt_secret, timedelta(minutes=settings.access_token_ttl_minutes), clock
    )


@pytest.fixture
def create_tenant(client: httpx.AsyncClient, settings: Settings, master_engine: AsyncEngine):
    """Provisions a store the way a SuperAdmin would, then logs its Owner in.

    There is no sign-up endpoint (PRD §3.4), so this drives the same
    ``CreateTenant`` use case the ``apexwms create-tenant`` CLI does.
    """
    from domain.entities import User
    from infrastructure.persistence.mappers import AutoMapper, TenantMapper
    from infrastructure.persistence.master.models import TenantModel, UserModel
    from infrastructure.persistence.master.uow import SqlMasterUnitOfWork
    from infrastructure.persistence.repositories import MasterSqlRepository
    from infrastructure.provisioning import DefaultTenantProvisioner
    from infrastructure.security.password import Argon2PasswordHasher

    async def _create(
        name: str = "Acme Phones",
        slug: str = "acme",
        email: str = "owner@example.com",
        timezone: str = "Asia/Tashkent",
        password: str | None = None,
        full_name: str = "Test Owner",
    ) -> Tenant:
        async with _master_sessions(master_engine)() as session:
            clock = SystemClock()
            handler = CreateTenantHandler(
                tenants=MasterSqlRepository(session, TenantModel, TenantMapper()),
                users=MasterSqlRepository(session, UserModel, AutoMapper(User, UserModel)),
                hasher=Argon2PasswordHasher(),
                tokens=_token_service(settings, clock),
                provisioner=DefaultTenantProvisioner(master_engine, settings),
                clock=clock,
                uow=SqlMasterUnitOfWork(session),
                slugs=SlugNormalizer(),
                timezones=TimezoneValidator(),
            )
            result = await handler.handle(
                CreateTenantCommand(
                    name=name,
                    slug=slug,
                    owner_email=email,
                    owner_full_name=full_name,
                    timezone=timezone,
                )
            )

        data = result.data
        assert data is not None
        # Login needs no tenant header: the claim is stamped from users.tenant_id.
        temp = data.temporary_password
        resp = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": temp}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        tenant = Tenant(
            tenant_id=str(data.tenant_id),
            slug=slug,
            email=email,
            password=temp,
            user_id=str(data.owner_user_id),
            full_name=full_name,
            access_token=body["accessToken"],
            refresh_token=body["refreshToken"],
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
            body = resp.json()["data"]
            tenant.password = password
            tenant.access_token = body["accessToken"]
            tenant.refresh_token = body["refreshToken"]

        return tenant

    return _create


@pytest.fixture
def create_superadmin(settings: Settings, master_engine: AsyncEngine):
    """A platform operator: no home store, so their token carries no tenant."""
    from domain.entities import User
    from infrastructure.persistence.mappers import AutoMapper, UserAppRoleMapper
    from infrastructure.persistence.master.models import UserAppRoleModel, UserModel
    from infrastructure.persistence.master.uow import SqlMasterUnitOfWork
    from infrastructure.persistence.repositories import MasterSqlRepository
    from infrastructure.security.password import Argon2PasswordHasher

    async def _create(email: str = "ops@example.com", name: str = "Ops") -> tuple[str, str]:
        async with _master_sessions(master_engine)() as session:
            clock = SystemClock()
            handler = CreateSuperAdminHandler(
                users=MasterSqlRepository(session, UserModel, AutoMapper(User, UserModel)),
                app_roles=MasterSqlRepository(session, UserAppRoleModel, UserAppRoleMapper()),
                hasher=Argon2PasswordHasher(),
                tokens=_token_service(settings, clock),
                clock=clock,
                uow=SqlMasterUnitOfWork(session),
            )
            result = await handler.handle(CreateSuperAdminCommand(email=email, full_name=name))
        data = result.data
        assert data is not None
        return email, data.temporary_password

    return _create


@pytest.fixture
def grant_access(settings: Settings, master_engine: AsyncEngine):
    """Give a user access to a second store — the multi-store switching case."""
    from uuid import UUID

    from domain.entities import UserTenantAccess
    from infrastructure.persistence.mappers import AutoMapper
    from infrastructure.persistence.master.models import UserTenantAccessModel
    from infrastructure.persistence.master.uow import SqlMasterUnitOfWork
    from infrastructure.persistence.repositories import MasterSqlRepository

    async def _grant(user_id: str, tenant_id: str) -> None:
        from uuid import uuid4

        async with _master_sessions(master_engine)() as session:
            mapper = AutoMapper(UserTenantAccess, UserTenantAccessModel)
            await MasterSqlRepository(session, UserTenantAccessModel, mapper).add(
                UserTenantAccess(id=uuid4(), user_id=UUID(user_id), tenant_id=UUID(tenant_id))
            )
            await SqlMasterUnitOfWork(session).commit()

    return _grant
