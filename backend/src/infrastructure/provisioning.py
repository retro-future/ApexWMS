"""Tenant provisioning — the PRD §3.4 state machine, steps 2–5 idempotent.

    pending → provisioning → active | failed

Each step tolerates having already run, so a FAILED tenant can simply be
provisioned again. Status updates commit in their own transactions so a
crash mid-way leaves an honest status behind.
"""

import contextlib
import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from application.dtos import OwnerSeed
from application.errors import ProvisioningFailedError
from domain.roles import TenantRole
from domain.tenancy import TenantStatus
from infrastructure import migrations
from infrastructure.config import Settings
from infrastructure.persistence.master.models import TenantDatabaseModel, TenantModel
from infrastructure.persistence.tenant.models import (
    EmployeeModel,
    LocationModel,
    TenantSettingsModel,
)
from infrastructure.persistence.tenant.repositories import SETTINGS_ROW_ID
from infrastructure.tenancy import tenant_db_url

_DUPLICATE_DATABASE_SQLSTATE = "42P04"
DEFAULT_LOCATION_NAME = "Main Store"


class DefaultTenantProvisioner:
    """Implements the application ``TenantProvisioner`` port."""

    def __init__(self, master_engine: AsyncEngine, settings: Settings) -> None:
        self._engine = master_engine
        self._sessions = async_sessionmaker(master_engine, expire_on_commit=False)
        self._settings = settings

    async def provision(
        self, tenant_id: UUID, timezone: str, owner: OwnerSeed | None = None
    ) -> None:
        """*owner* is None only when re-provisioning a tenant that already has
        one — the seed step is idempotent either way."""
        try:
            await self._set_status(tenant_id, TenantStatus.PROVISIONING)
            db_name = f"{self._settings.tenant_db_name_prefix}{tenant_id.hex}"
            await self._create_database(db_name)
            await self._record_database(tenant_id, db_name)
            url = tenant_db_url(self._settings.master_db_url, db_name)
            await migrations.upgrade("tenant", url)
            await self._seed(url, timezone, owner)
            await self._set_status(tenant_id, TenantStatus.ACTIVE)
        except Exception as exc:
            # Best-effort status update; the original failure is the one to raise.
            with contextlib.suppress(Exception):
                await self._set_status(tenant_id, TenantStatus.FAILED)
            raise ProvisioningFailedError(f"provisioning tenant {tenant_id} failed") from exc

    async def _set_status(self, tenant_id: UUID, status: TenantStatus) -> None:
        async with self._sessions() as session:
            tenant = await session.get(TenantModel, tenant_id)
            if tenant is None:
                raise LookupError(f"tenant {tenant_id} does not exist")
            tenant.status = status.value
            await session.commit()

    async def _create_database(self, db_name: str) -> None:
        # CREATE DATABASE cannot run inside a transaction — Postgres requires
        # autocommit. An already-existing database means a previous attempt
        # got this far; that's fine (idempotency).
        async with self._engine.connect() as conn:
            autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
            try:
                await autocommit.execute(text(f'CREATE DATABASE "{db_name}"'))
            except DBAPIError as exc:
                if getattr(exc.orig, "sqlstate", None) != _DUPLICATE_DATABASE_SQLSTATE:
                    raise

    async def _record_database(self, tenant_id: UUID, db_name: str) -> None:
        async with self._sessions() as session:
            existing = await session.get(TenantDatabaseModel, tenant_id)
            if existing is None:
                tenant = await session.get(TenantModel, tenant_id)
                if tenant is None:
                    raise LookupError(f"tenant {tenant_id} does not exist")
                session.add(
                    TenantDatabaseModel(
                        tenant_id=tenant_id, db_name=db_name, created_at=tenant.created_at
                    )
                )
                await session.commit()

    async def _seed(self, url: str, timezone: str, owner: OwnerSeed | None) -> None:
        engine = create_async_engine(url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                if await session.get(TenantSettingsModel, SETTINGS_ROW_ID) is None:
                    session.add(TenantSettingsModel(id=SETTINGS_ROW_ID, timezone=timezone))
                has_location = (
                    await session.execute(text("SELECT 1 FROM locations LIMIT 1"))
                ).first()
                if has_location is None:
                    session.add(
                        LocationModel(
                            id=uuid.uuid4(),
                            name=DEFAULT_LOCATION_NAME,
                            is_active=True,
                            created_at=datetime.now(UTC),
                        )
                    )
                await self._seed_owner(session, owner)
                await session.commit()
        finally:
            await engine.dispose()

    async def _seed_owner(self, session: AsyncSession, owner: OwnerSeed | None) -> None:
        """The Owner's presence at this store — the only way in, sign-up is gone.

        The matching login identity is a master ``users`` row written by
        ``CreateTenant``; the id is carried across so the two match, which is
        what the ledger's foreign keys will depend on from M3.
        """
        if owner is None:
            return
        has_employee = (
            await session.execute(text("SELECT 1 FROM employees LIMIT 1"))
        ).first()
        if has_employee is not None:
            return
        session.add(
            EmployeeModel(
                id=owner.user_id,
                email=owner.email,
                full_name=owner.full_name,
                role=TenantRole.OWNER.value,
                is_active=True,
                created_at=datetime.now(UTC),
            )
        )
