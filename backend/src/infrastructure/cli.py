"""The ``apexwms`` operations CLI — the SuperAdmin surface (PRD §3.4).

    apexwms migrate-master                 # MasterDB → head
    apexwms migrate --all-tenants          # fan out over every tenant DB
    apexwms migrate --tenant <uuid>        # one tenant
    apexwms create-tenant --name ... --slug ... --owner-email ...
    apexwms create-superadmin --email ... --name ...
    apexwms list-tenants
    apexwms suspend-tenant <uuid> | apexwms activate-tenant <uuid>
    apexwms retry-provisioning <uuid> [--timezone tz]
    apexwms seed-tenant <uuid> [--products N] [--customers N] [--suppliers N]
    apexwms verify-projections --all-tenants | --tenant <uuid>
    apexwms verify-financials  --all-tenants | --tenant <uuid>
    apexwms verify-balances    --all-tenants | --tenant <uuid>

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
from application.services import SlugNormalizer, TimezoneValidator
from domain.enums import AppRole, TenantStatus
from infrastructure import migrations
from infrastructure.config import Settings
from infrastructure.persistence.master.models import TenantDatabaseModel, TenantModel
from infrastructure.tenancy import tenant_db_url
from infrastructure.types import MasterSession, TenantSession

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

    seed = sub.add_parser(
        "seed-tenant", help="fill a tenant's catalog with fake demo data (dev/demo only)"
    )
    seed.add_argument("tenant_id", type=UUID)
    seed.add_argument("--products", type=int, default=30)
    seed.add_argument("--customers", type=int, default=20)
    seed.add_argument("--suppliers", type=int, default=5)
    seed.add_argument("--seed", type=int, default=None, help="random seed, for reproducible data")

    # The three audits (PRD §11, FR-10.7, FR-10.7b). Same target flags as
    # ``migrate``, because they answer the same shape of question about the
    # same fleet.
    for name, help_text in (
        ("verify-projections", "recompute stock projections from the ledger"),
        ("verify-financials", "reconcile inventory value against the money ledger"),
        ("verify-balances", "recompute customer debt from invoices and payments"),
    ):
        verify = sub.add_parser(name, help=help_text)
        scope = verify.add_mutually_exclusive_group(required=True)
        scope.add_argument("--all-tenants", action="store_true")
        scope.add_argument("--tenant", type=UUID, metavar="TENANT_ID")

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
    if args.command == "seed-tenant":
        return asyncio.run(_seed_tenant(settings, args))
    if args.command in ("verify-projections", "verify-financials", "verify-balances"):
        tenant_id = None if args.all_tenants else args.tenant
        return asyncio.run(_verify(settings, args.command, tenant_id))
    return 2


async def _create_tenant(settings: Settings, args: argparse.Namespace) -> int:
    # Local imports: provisioning pulls in the tenant models and Alembic.
    from domain.entities import User
    from infrastructure.clock import SystemClock
    from infrastructure.persistence.mappers import AutoMapper, TenantMapper
    from infrastructure.persistence.master.models import TenantModel, UserModel
    from infrastructure.persistence.master.uow import SqlMasterUnitOfWork
    from infrastructure.persistence.repositories import MasterSqlRepository
    from infrastructure.provisioning import DefaultTenantProvisioner
    from infrastructure.security.password import Argon2PasswordHasher
    from infrastructure.security.tokens import JwtTokenService

    engine = create_async_engine(settings.master_db_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            master = MasterSession(session)
            clock = SystemClock()
            handler = CreateTenantHandler(
                tenants=MasterSqlRepository(master, TenantModel, TenantMapper()),
                users=MasterSqlRepository(master, UserModel, AutoMapper(User, UserModel)),
                hasher=Argon2PasswordHasher(),
                tokens=JwtTokenService(
                    settings.jwt_secret,
                    timedelta(minutes=settings.access_token_ttl_minutes),
                    clock,
                ),
                provisioner=DefaultTenantProvisioner(engine, settings),
                clock=clock,
                uow=SqlMasterUnitOfWork(master),
                slugs=SlugNormalizer(),
                timezones=TimezoneValidator(),
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
    from domain.entities import User
    from infrastructure.clock import SystemClock
    from infrastructure.persistence.mappers import AutoMapper, UserAppRoleMapper
    from infrastructure.persistence.master.models import UserAppRoleModel, UserModel
    from infrastructure.persistence.master.uow import SqlMasterUnitOfWork
    from infrastructure.persistence.repositories import MasterSqlRepository
    from infrastructure.security.password import Argon2PasswordHasher
    from infrastructure.security.tokens import JwtTokenService

    engine = create_async_engine(settings.master_db_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            master = MasterSession(session)
            clock = SystemClock()
            handler = CreateSuperAdminHandler(
                users=MasterSqlRepository(master, UserModel, AutoMapper(User, UserModel)),
                app_roles=MasterSqlRepository(master, UserAppRoleModel, UserAppRoleMapper()),
                hasher=Argon2PasswordHasher(),
                tokens=JwtTokenService(
                    settings.jwt_secret,
                    timedelta(minutes=settings.access_token_ttl_minutes),
                    clock,
                ),
                clock=clock,
                uow=SqlMasterUnitOfWork(master),
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
    rows = await _tenant_databases(settings, tenant_id)
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


async def _verify(settings: Settings, command: str, tenant_id: UUID | None) -> int:
    """Fan the three audits out over the fleet (PRD §11, FR-10.7, FR-10.7b).

    Same shape as the migration fan-out: continue past a tenant that
    cannot be reached, report everything at the end, exit non-zero if
    anything is wrong. **A discrepancy is reported, never repaired** — the
    ledger is the source of truth, and a sweep that quietly rewrote
    projections would destroy the evidence of whatever wrote them wrong.
    """
    rows = await _tenant_databases(settings, tenant_id)
    if not rows:
        print("no tenant databases found")
        return 0

    total_findings = 0
    unreachable: list[tuple[UUID, str]] = []
    for row in rows:
        url = tenant_db_url(settings.master_db_url, row.db_name)
        try:
            findings = await _verify_one(url, command)
        except Exception as exc:  # noqa: BLE001 - fan-out must continue past failures
            unreachable.append((row.tenant_id, str(exc)))
            print(f"  FAILED  {row.tenant_id}: {exc}")
            continue

        if findings:
            total_findings += len(findings)
            print(f"  MISMATCH {row.tenant_id}: {len(findings)} discrepancy(ies)")
            for finding in findings:
                print(f"      {finding}")
        else:
            print(f"  ok      {row.tenant_id}")

    print(f"\n{len(rows)} tenant database(s) checked")
    if total_findings or unreachable:
        print(f"{total_findings} discrepancy(ies), {len(unreachable)} unreachable")
        return 1
    print("everything reconciles")
    return 0


async def _verify_one(url: str, command: str) -> list[str]:
    """Run one audit against one store's database.

    Hand-wired rather than resolved from the container: the CLI has no
    request, so there is no ``REQUEST`` scope to resolve these in — the
    same reason ``create-tenant`` builds its handler by hand. The
    ``TenantSession`` wrapper is not cosmetic; it is what stops a master
    session reaching a tenant repository (``infrastructure/types.py``).
    """
    from application.services import (
        BalanceVerifier,
        CostPoolReader,
        LedgerReconciler,
        ProjectionVerifier,
    )
    from domain.entities import StockLevel
    from domain.services import UnitProjector
    from infrastructure.persistence.mappers import (
        AutoMapper,
        DeviceUnitMapper,
        DeviceUnitPriceChangeMapper,
        FinancialTransactionMapper,
        PaymentMapper,
        ProductMapper,
        ProductPriceChangeMapper,
        SalesInvoiceMapper,
        StockMovementMapper,
    )
    from infrastructure.persistence.repositories import (
        TenantSqlAppendOnlyRepository,
        TenantSqlRepository,
    )
    from infrastructure.persistence.tenant.models import (
        DeviceUnitModel,
        DeviceUnitPriceChangeModel,
        FinancialTransactionModel,
        PaymentModel,
        ProductModel,
        ProductPriceChangeModel,
        SalesInvoiceModel,
        StockLevelModel,
        StockMovementModel,
    )
    from infrastructure.persistence.tenant.queries import (
        SqlFinancialTransactionQueries,
        SqlStockMovementQueries,
    )

    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine)() as raw:
            session = TenantSession(raw)
            units = TenantSqlRepository(session, DeviceUnitModel, DeviceUnitMapper())
            movements = TenantSqlAppendOnlyRepository(
                session, StockMovementModel, StockMovementMapper()
            )
            movement_queries = SqlStockMovementQueries(session)
            transactions = TenantSqlAppendOnlyRepository(
                session, FinancialTransactionModel, FinancialTransactionMapper()
            )
            transaction_queries = SqlFinancialTransactionQueries(session)
            products = TenantSqlRepository(session, ProductModel, ProductMapper())
            levels = TenantSqlRepository(
                session, StockLevelModel, AutoMapper(StockLevel, StockLevelModel)
            )
            if command == "verify-balances":
                balances = BalanceVerifier(
                    TenantSqlRepository(
                        session, SalesInvoiceModel, SalesInvoiceMapper()
                    ),
                    TenantSqlAppendOnlyRepository(session, PaymentModel, PaymentMapper()),
                    transaction_queries,
                )
                return [str(finding) for finding in await balances.verify()]

            if command == "verify-financials":
                checker = LedgerReconciler(
                    units,
                    transaction_queries,
                    movement_queries,
                    CostPoolReader(products, movements, transactions),
                )
                return [str(finding) for finding in await checker.reconcile()]

            verifier = ProjectionVerifier(
                movements,
                movement_queries,
                levels,
                units,
                TenantSqlAppendOnlyRepository(
                    session, DeviceUnitPriceChangeModel, DeviceUnitPriceChangeMapper()
                ),
                products,
                TenantSqlAppendOnlyRepository(
                    session, ProductPriceChangeModel, ProductPriceChangeMapper()
                ),
                UnitProjector(),
            )
            return [str(finding) for finding in await verifier.verify()]
    finally:
        await engine.dispose()


async def _tenant_databases(
    settings: Settings, tenant_id: UUID | None
) -> list[TenantDatabaseModel]:
    engine = create_async_engine(settings.master_db_url)
    try:
        async with async_sessionmaker(engine)() as session:
            query = select(TenantDatabaseModel)
            if tenant_id is not None:
                query = query.where(TenantDatabaseModel.tenant_id == tenant_id)
            return list((await session.scalars(query)).all())
    finally:
        await engine.dispose()


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


async def _seed_tenant(settings: Settings, args: argparse.Namespace) -> int:
    # Local import: seeding pulls in Faker, a dev-only dependency.
    from infrastructure.seeding import seed_catalog

    engine = create_async_engine(settings.master_db_url)
    try:
        async with async_sessionmaker(engine)() as session:
            row = await session.get(TenantDatabaseModel, args.tenant_id)
    finally:
        await engine.dispose()

    if row is None:
        print(f"no such tenant database: {args.tenant_id}", file=sys.stderr)
        print(
            "(has this tenant finished provisioning? see `apexwms list-tenants`)",
            file=sys.stderr,
        )
        return 1

    url = tenant_db_url(settings.master_db_url, row.db_name)
    summary = await seed_catalog(
        url,
        products=args.products,
        customers=args.customers,
        suppliers=args.suppliers,
        seed=args.seed,
    )
    print(f"tenant {args.tenant_id} seeded:")
    print(f"  products:  {summary.products_created}")
    print(f"  customers: {summary.customers_created}")
    print(f"  suppliers: {summary.suppliers_created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
