"""Fake catalog data for a provisioned tenant (dev/demo use only).

Not business logic for any milestone — a thin fan-out over the same
command handlers ``presentation/routers/products.py`` etc. call, so a
seeded row passes exactly the validation a real request would (SKU
format, GS1 barcode check digit, uniqueness). Nothing here writes a row
directly with SQLAlchemy.

Faker is a dev-only dependency (see ``[dependency-groups].dev`` in
pyproject.toml) and is imported lazily so importing this module never
requires it outside a development environment.

Safe to re-run against the same tenant: a SKU/barcode/name collision from
a previous run raises the same ``ApplicationError`` a duplicate API call
would, which is caught and skipped rather than aborting the batch —
mirroring the fan-out idempotency of ``apexwms migrate --all-tenants``.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from application.commands.create_customer import CreateCustomerCommand, CreateCustomerHandler
from application.commands.create_product import CreateProductCommand, CreateProductHandler
from application.commands.create_supplier import CreateSupplierCommand, CreateSupplierHandler
from application.errors import ApplicationError
from application.services import SalePriceParser
from domain.enums import TrackingType
from infrastructure.clock import SystemClock
from infrastructure.persistence.tenant.repositories import (
    SqlCustomerRepository,
    SqlProductRepository,
    SqlSupplierRepository,
)
from infrastructure.persistence.tenant.uow import SqlTenantUnitOfWork
from infrastructure.types import TenantSession

# FR-2.6: phones are SERIAL/USD, accessories are QUANTITY/UZS (see
# domain/entities/product.py). One in three products seeded is a phone.
_PHONE_MODELS: dict[str, list[str]] = {
    "Apple": ["iPhone 13", "iPhone 14", "iPhone 15", "iPhone 15 Pro"],
    "Samsung": ["Galaxy S23", "Galaxy S24", "Galaxy A54", "Galaxy Z Flip5"],
    "Xiaomi": ["Redmi Note 12", "Redmi Note 13 Pro", "13T", "Poco X6"],
}
# (name, brand) — a SERIAL product may not carry a barcode (it is
# identified by IMEI, FR-2.3), so only these get one.
_ACCESSORIES: list[tuple[str, str]] = [
    ("Silicone Case", "Generic"),
    ("Tempered Glass Screen Protector", "Generic"),
    ("20W USB-C Fast Charger", "Anker"),
    ("USB-C to USB-C Cable 1m", "Baseus"),
    ("Wireless Earbuds", "QCY"),
    ("Power Bank 10000mAh", "Xiaomi"),
    ("Car Phone Mount", "Generic"),
    ("Bluetooth Speaker", "JBL"),
]


@dataclass(frozen=True, slots=True)
class SeedSummary:
    products_created: int
    customers_created: int
    suppliers_created: int


async def seed_catalog(
    tenant_db_url: str,
    *,
    products: int = 30,
    customers: int = 20,
    suppliers: int = 5,
    seed: int | None = None,
) -> SeedSummary:
    """Fill an already-provisioned, already-migrated tenant database with
    realistic-looking products, customers and suppliers, for exercising
    the API by hand (Swagger, curl, ...) rather than with empty tables.
    """
    from faker import Faker  # local import: dev-only dependency

    fake = Faker()
    if seed is not None:
        Faker.seed(seed)

    engine = create_async_engine(tenant_db_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            tenant_session = TenantSession(session)
            clock = SystemClock()
            uow = SqlTenantUnitOfWork(tenant_session)

            product_handler = CreateProductHandler(
                products=SqlProductRepository(tenant_session),
                clock=clock,
                uow=uow,
                sale_price=SalePriceParser(),
            )
            customer_handler = CreateCustomerHandler(
                customers=SqlCustomerRepository(tenant_session), clock=clock, uow=uow
            )
            supplier_handler = CreateSupplierHandler(
                suppliers=SqlSupplierRepository(tenant_session), clock=clock, uow=uow
            )

            created_products = await _seed_products(product_handler, fake, products)
            created_customers = await _seed_customers(customer_handler, fake, customers)
            created_suppliers = await _seed_suppliers(supplier_handler, fake, suppliers)
    finally:
        await engine.dispose()

    return SeedSummary(
        products_created=created_products,
        customers_created=created_customers,
        suppliers_created=created_suppliers,
    )


async def _seed_products(handler: CreateProductHandler, fake, count: int) -> int:
    created = 0
    for i in range(count):
        if i % 3 == 0:
            brand = fake.random_element(list(_PHONE_MODELS))
            model = fake.random_element(_PHONE_MODELS[brand])
            command = CreateProductCommand(
                sku=f"PHN-{i:04d}",
                name=f"{brand} {model}",
                brand=brand,
                model=model,
                tracking_type=TrackingType.SERIAL,
                default_sale_price=str(fake.random_int(min=150, max=1500)),
            )
        else:
            name, brand = fake.random_element(_ACCESSORIES)
            command = CreateProductCommand(
                sku=f"ACC-{i:04d}",
                name=name,
                brand=brand,
                tracking_type=TrackingType.QUANTITY,
                barcode=fake.ean13(),
                default_sale_price=str(fake.random_int(min=20_000, max=500_000)),
            )
        try:
            await handler.handle(command)
            created += 1
        except ApplicationError:
            continue
    return created


async def _seed_customers(handler: CreateCustomerHandler, fake, count: int) -> int:
    created = 0
    for _ in range(count):
        command = CreateCustomerCommand(full_name=fake.name(), phone=fake.phone_number())
        try:
            await handler.handle(command)
            created += 1
        except ApplicationError:
            continue
    return created


async def _seed_suppliers(handler: CreateSupplierHandler, fake, count: int) -> int:
    created = 0
    for _ in range(count):
        command = CreateSupplierCommand(
            name=fake.unique.company(),
            contact_name=fake.name(),
            phone=fake.phone_number(),
            email=fake.company_email(),
        )
        try:
            await handler.handle(command)
            created += 1
        except ApplicationError:
            continue
    return created
