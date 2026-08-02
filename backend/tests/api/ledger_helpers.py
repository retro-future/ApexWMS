"""Putting stock into a real tenant database, for the M3 API suites.

M4's Goods Receipt has no HTTP surface yet, so a test that needs a handset
on the shelf posts the receipt M4 will post — through ``LedgerPoster``,
against the same migrated Postgres the API serves from. That is deliberate
rather than a shortcut: writing the rows directly would skip the very
machinery these suites exist to prove.
"""

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from application.dtos import CurrentUser, MoneyEffect, Posting, PostingEntry
from application.services import LedgerPoster
from domain.entities import DeviceUnit
from domain.enums import (
    DeviceCondition,
    DeviceStatus,
    DocumentType,
    MovementType,
    TransactionType,
)
from domain.value_objects import IMEI, Currency, Money
from infrastructure.clock import SystemClock
from infrastructure.persistence.master.models import TenantDatabaseModel
from infrastructure.persistence.tenant.models import LocationModel
from infrastructure.persistence.tenant.repositories import (
    SqlDeviceUnitRepository,
    SqlFinancialTransactionRepository,
    SqlStockLevelRepository,
    SqlStockMovementRepository,
)
from infrastructure.persistence.tenant.uow import SqlTenantUnitOfWork
from infrastructure.tenancy import tenant_db_url
from infrastructure.types import TenantSession

PASSWORD = "hunter2000"
PHONE_IMEI = "490154203237518"


def usd(major: str) -> Money:
    return Money.from_major(major, Currency.USD)


async def tenant_url(settings, tenant_id: str) -> str:
    engine = create_async_engine(settings.master_db_url)
    try:
        async with AsyncSession(engine) as session:
            row = await session.get(TenantDatabaseModel, UUID(tenant_id))
            assert row is not None, "provisioning recorded no tenant_databases row"
            return tenant_db_url(settings.master_db_url, row.db_name)
    finally:
        await engine.dispose()


async def receive_phone(client, settings, owner, *, cost="380", condition="used", **unit):
    """Post the receipt M4 will post, against the real tenant database.

    Returns ``(device_unit_id, product_id, location_id)``. The Owner is the
    acting user because the ledger's ``user_id`` is a foreign key into
    ``employees`` — the "``Employee.id`` *is* ``User.id``" contract (§3.1),
    exercised for real rather than asserted in prose.
    """
    created = await client.post(
        "/api/v1/products",
        headers=owner.auth,
        json={
            "sku": f"IP15P-{uuid4().hex[:6]}",
            "name": "iPhone 15 Pro",
            "trackingType": "serial",
        },
    )
    assert created.status_code == 201, created.text
    product_id = UUID(created.json()["data"]["id"])

    engine = create_async_engine(await tenant_url(settings, owner.tenant_id))
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as raw:
            session = TenantSession(raw)
            location_id = (await raw.scalars(select(LocationModel.id))).first()

            units = SqlDeviceUnitRepository(session)
            unit_id = uuid4()
            await units.add(
                DeviceUnit(
                    id=unit_id,
                    imei=IMEI(unit.pop("imei", PHONE_IMEI)),
                    product_id=product_id,
                    status=DeviceStatus.IN_STOCK,
                    location_id=location_id,
                    acquisition_cost=usd(cost),
                    condition=DeviceCondition(condition),
                    created_at=SystemClock().now(),
                    **unit,
                )
            )

            poster = LedgerPoster(
                SqlStockMovementRepository(session),
                SqlFinancialTransactionRepository(session),
                SqlStockLevelRepository(session),
                units,
                SystemClock(),
                CurrentUser(user_id=UUID(owner.user_id), permissions=frozenset()),
            )
            await poster.post(
                Posting(
                    document_type=DocumentType.GOODS_RECEIPT,
                    document_id=uuid4(),
                    entries=[
                        PostingEntry(
                            movement_type=MovementType.RECEIPT,
                            product_id=product_id,
                            location_id=location_id,
                            quantity_delta=1,
                            device_unit_id=unit_id,
                            new_status=DeviceStatus.IN_STOCK,
                            new_location_id=location_id,
                            money=[MoneyEffect(TransactionType.PURCHASE, -usd(cost))],
                        )
                    ],
                )
            )
            await SqlTenantUnitOfWork(session).commit()
        return unit_id, product_id, location_id
    finally:
        await engine.dispose()
