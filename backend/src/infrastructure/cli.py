"""The ``apexwms`` operations CLI.

    apexwms migrate-master                 # MasterDB → head
    apexwms migrate --all-tenants          # fan out over every tenant DB
    apexwms migrate --tenant <uuid>        # one tenant
    apexwms retry-provisioning <uuid> [--timezone tz]

The tenant fan-out is idempotent and resumable (PRD §3.2): it continues
past failures and reports the fleet's version spread at the end, because
a partially-migrated fleet is an expected state, not an emergency.
"""

import argparse
import asyncio
import sys
from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from infrastructure import migrations
from infrastructure.config import Settings
from infrastructure.persistence.master.models import TenantDatabaseModel
from infrastructure.tenancy import tenant_db_url


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="apexwms")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate-master", help="upgrade the master database to head")

    migrate = sub.add_parser("migrate", help="upgrade tenant databases to head")
    target = migrate.add_mutually_exclusive_group(required=True)
    target.add_argument("--all-tenants", action="store_true")
    target.add_argument("--tenant", type=UUID, metavar="TENANT_ID")

    retry = sub.add_parser("retry-provisioning", help="re-run provisioning for a failed tenant")
    retry.add_argument("tenant_id", type=UUID)
    retry.add_argument("--timezone", default="Asia/Tashkent")

    args = parser.parse_args(argv)
    settings = Settings()

    if args.command == "migrate-master":
        migrations.upgrade_sync("master", settings.master_db_url)
        print("master: upgraded to head")
        return 0
    if args.command == "migrate":
        tenant_id = None if args.all_tenants else args.tenant
        return asyncio.run(_migrate_tenants(settings, tenant_id))
    if args.command == "retry-provisioning":
        return asyncio.run(_retry_provisioning(settings, args.tenant_id, args.timezone))
    return 2


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
