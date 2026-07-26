"""The ``apexwms`` operations CLI — the SuperAdmin surface (PRD §3.4).

    apexwms migrate-master                 # MasterDB → head
    apexwms migrate --all-tenants          # fan out over every tenant DB
    apexwms migrate --tenant <uuid>        # one tenant
    apexwms create-tenant --name ... --slug ... --owner-email ...
    apexwms create-superadmin --email ... --name ...
    apexwms list-tenants
    apexwms suspend-tenant <uuid> | apexwms activate-tenant <uuid>
    apexwms retry-provisioning <uuid> [--timezone tz]

There is no HTTP admin API in the MVP: shell access to the server plus the
MasterDB URL *is* the SuperAdmin credential. The admin portal, and the
separate auth realm it needs, are v2.

The tenant fan-out is idempotent and resumable (PRD §3.2): it continues
past failures and reports the fleet's version spread at the end, because
a partially-migrated fleet is an expected state, not an emergency.
"""

import argparse
import asyncio
import sys
from collections import Counter
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from application.commands.create_superadmin import (
    CreateSuperAdminCommand,
    CreateSuperAdminHandler,
)
from application.commands.create_tenant import CreateTenantCommand, CreateTenantHandler
from application.errors import ApplicationError
from domain.roles import AppRole
from domain.tenancy import TenantStatus
from infrastructure import migrations
from infrastructure.config import Settings
from infrastructure.persistence.master.models import TenantDatabaseModel, TenantModel
from infrastructure.tenancy import tenant_db_url

DEFAULT_TIMEZONE = "Asia/Tashkent"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="apexwms")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate-master", help="upgrade the master database to head")

    migrate = sub.add_parser("migrate", help="upgrade tenant databases to head")
    target = migrate.add_mutually_exclusive_group(required=True)
    target.add_argument("--all-tenants", action="store_true")
    target.add_argument("--tenant", type=UUID, metavar="TENANT_ID")

    create = sub.add_parser("create-tenant", help="provision a new tenant and its Owner")
    create.add_argument("--name", required=True, help="display name, e.g. 'Acme Phones'")
    create.add_argument("--slug", required=True, help="login handle, e.g. 'acme'")
    create.add_argument("--owner-email", required=True)
    create.add_argument("--owner-name", required=True)
    create.add_argument("--timezone", default=DEFAULT_TIMEZONE)

    sub.add_parser("list-tenants", help="every tenant with its slug and status")

    superadmin = sub.add_parser(
        "create-superadmin", help="create a platform operator (no home store)"
    )
    superadmin.add_argument("--email", required=True)
    superadmin.add_argument("--name", required=True)
    superadmin.add_argument(
        "--role",
        default=AppRole.SUPERADMIN.value,
        choices=[role.value for role in AppRole],
    )

    suspend = sub.add_parser("suspend-tenant", help="block all access to a tenant")
    suspend.add_argument("tenant_id", type=UUID)
    activate = sub.add_parser("activate-tenant", help="restore access to a suspended tenant")
    activate.add_argument("tenant_id", type=UUID)

    retry = sub.add_parser("retry-provisioning", help="re-run provisioning for a failed tenant")
    retry.add_argument("tenant_id", type=UUID)
    retry.add_argument("--timezone", default=DEFAULT_TIMEZONE)

    args = parser.parse_args(argv)
    settings = Settings()

    if args.command == "migrate-master":
        migrations.upgrade_sync("master", settings.master_db_url)
        print("master: upgraded to head")
        return 0
    if args.command == "migrate":
        tenant_id = None if args.all_tenants else args.tenant
        return asyncio.run(_migrate_tenants(settings, tenant_id))
    if args.command == "create-tenant":
        return asyncio.run(_create_tenant(settings, args))
    if args.command == "list-tenants":
        return asyncio.run(_list_tenants(settings))
    if args.command == "create-superadmin":
        return asyncio.run(_create_superadmin(settings, args))
    if args.command == "suspend-tenant":
        return asyncio.run(_set_status(settings, args.tenant_id, TenantStatus.SUSPENDED))
    if args.command == "activate-tenant":
        return asyncio.run(_set_status(settings, args.tenant_id, TenantStatus.ACTIVE))
    if args.command == "retry-provisioning":
        return asyncio.run(_retry_provisioning(settings, args.tenant_id, args.timezone))
    return 2


async def _create_tenant(settings: Settings, args: argparse.Namespace) -> int:
    # Local imports: provisioning pulls in the tenant models and Alembic.
    from infrastructure.clock import SystemClock
    from infrastructure.persistence.master.repositories import (
        SqlTenantRepository,
        SqlUserRepository,
    )
    from infrastructure.persistence.master.uow import SqlMasterUnitOfWork
    from infrastructure.provisioning import DefaultTenantProvisioner
    from infrastructure.security.password import Argon2PasswordHasher
    from infrastructure.security.tokens import JwtTokenService

    engine = create_async_engine(settings.master_db_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            clock = SystemClock()
            handler = CreateTenantHandler(
                tenants=SqlTenantRepository(session),
                users=SqlUserRepository(session),
                hasher=Argon2PasswordHasher(),
                tokens=JwtTokenService(
                    settings.jwt_secret,
                    timedelta(minutes=settings.access_token_ttl_minutes),
                    clock,
                ),
                provisioner=DefaultTenantProvisioner(engine, settings),
                clock=clock,
                uow=SqlMasterUnitOfWork(session),
            )
            result = await handler.handle(
                CreateTenantCommand(
                    name=args.name,
                    slug=args.slug,
                    owner_email=args.owner_email,
                    owner_full_name=args.owner_name,
                    timezone=args.timezone,
                )
            )
    except ApplicationError as exc:
        print(f"could not create tenant: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()

    data = result.data
    assert data is not None
    print(f"tenant {data.tenant_id} is active")
    print(f"  slug:               {data.slug}")
    print(f"  owner:              {data.owner_email}")
    print(f"  temporary password: {data.temporary_password}")
    print("\nThe Owner logs in with email and password alone — the store is")
    print("stamped into their token server-side. They must change this password")
    print("immediately; it is not stored anywhere and cannot be shown again.")
    return 0


async def _create_superadmin(settings: Settings, args: argparse.Namespace) -> int:
    from infrastructure.clock import SystemClock
    from infrastructure.persistence.master.repositories import (
        SqlUserAppRoleRepository,
        SqlUserRepository,
    )
    from infrastructure.persistence.master.uow import SqlMasterUnitOfWork
    from infrastructure.security.password import Argon2PasswordHasher
    from infrastructure.security.tokens import JwtTokenService

    engine = create_async_engine(settings.master_db_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            clock = SystemClock()
            handler = CreateSuperAdminHandler(
                users=SqlUserRepository(session),
                app_roles=SqlUserAppRoleRepository(session),
                hasher=Argon2PasswordHasher(),
                tokens=JwtTokenService(
                    settings.jwt_secret,
                    timedelta(minutes=settings.access_token_ttl_minutes),
                    clock,
                ),
                clock=clock,
                uow=SqlMasterUnitOfWork(session),
            )
            result = await handler.handle(
                CreateSuperAdminCommand(
                    email=args.email, full_name=args.name, role=AppRole(args.role)
                )
            )
    except ApplicationError as exc:
        print(f"could not create operator: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()

    data = result.data
    assert data is not None
    print(f"{args.role} {data.user_id} created")
    print(f"  email:              {data.email}")
    print(f"  temporary password: {data.temporary_password}")
    print("\nThey log in with no tenant header and must change this password")
    print("immediately. It is not stored anywhere and cannot be shown again.")
    return 0


async def _list_tenants(settings: Settings) -> int:
    engine = create_async_engine(settings.master_db_url)
    try:
        async with async_sessionmaker(engine)() as session:
            rows = (
                await session.scalars(select(TenantModel).order_by(TenantModel.created_at))
            ).all()
    finally:
        await engine.dispose()

    if not rows:
        print("no tenants")
        return 0
    for row in rows:
        print(f"  {row.id}  {row.slug:<20} {row.status:<13} {row.name}")
    print(f"\n{len(rows)} tenant(s)")
    return 0


async def _set_status(settings: Settings, tenant_id: UUID, status: TenantStatus) -> int:
    engine = create_async_engine(settings.master_db_url)
    try:
        async with async_sessionmaker(engine)() as session:
            tenant = await session.get(TenantModel, tenant_id)
            if tenant is None:
                print(f"no such tenant: {tenant_id}", file=sys.stderr)
                return 1
            tenant.status = status.value
            await session.commit()
    finally:
        await engine.dispose()
    print(f"tenant {tenant_id}: {status.value}")
    return 0


async def _migrate_tenants(settings: Settings, tenant_id: UUID | None) -> int:
    engine = create_async_engine(settings.master_db_url)
    try:
        async with async_sessionmaker(engine)() as session:
            query = select(TenantDatabaseModel)
            if tenant_id is not None:
                query = query.where(TenantDatabaseModel.tenant_id == tenant_id)
            rows = (await session.scalars(query)).all()
    finally:
        await engine.dispose()

    if not rows:
        print("no tenant databases found")
        return 0

    versions: Counter[str] = Counter()
    failures: list[tuple[UUID, str]] = []
    for row in rows:
        url = tenant_db_url(settings.master_db_url, row.db_name)
        try:
            await migrations.upgrade("tenant", url)
            revision = await migrations.current_revision(url) or "<none>"
            versions[revision] += 1
            print(f"  ok      {row.tenant_id}  @ {revision}")
        except Exception as exc:  # noqa: BLE001 - fan-out must continue past failures
            versions[await _safe_revision(url)] += 1
            failures.append((row.tenant_id, str(exc)))
            print(f"  FAILED  {row.tenant_id}: {exc}")

    print(f"\n{len(rows)} tenant database(s); version spread:")
    for revision, count in versions.most_common():
        print(f"  {revision}: {count}")
    if failures:
        print(f"\n{len(failures)} failure(s) — re-run to resume; the operation is idempotent.")
        return 1
    return 0


async def _safe_revision(url: str) -> str:
    try:
        return await migrations.current_revision(url) or "<none>"
    except Exception:  # noqa: BLE001
        return "<unreachable>"


async def _retry_provisioning(settings: Settings, tenant_id: UUID, timezone: str) -> int:
    # Local import: provisioning pulls in the tenant models and Alembic.
    from infrastructure.provisioning import DefaultTenantProvisioner

    engine = create_async_engine(settings.master_db_url)
    try:
        provisioner = DefaultTenantProvisioner(engine, settings)
        # No owner seed: a retry targets a tenant that was created with one.
        await provisioner.provision(tenant_id, timezone)
        print(f"tenant {tenant_id}: active")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"tenant {tenant_id}: provisioning failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
