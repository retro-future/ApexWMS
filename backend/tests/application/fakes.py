"""In-memory fakes for the application ports (PRD §9 Testing:
use cases are tested with no database at all).

The split mirrors the real one: ``FakeUserRepository`` and friends stand
for MasterDB, ``FakeEmployeeRepository`` for one store's database, and
``FakeTenantScope`` for reaching a store the edge did not resolve.
"""

import hashlib
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from application.dtos import OwnerSeed, RefreshTokenParts
from application.errors import ProvisioningFailedError, TenantNotActiveError
from domain.core import Entity
from domain.entities import (
    Customer,
    DeviceUnit,
    DeviceUnitPriceChange,
    Employee,
    FinancialTransaction,
    GoodsReceipt,
    Invitation,
    Location,
    Product,
    ProductPriceChange,
    PurchaseOrder,
    PurchaseOrderLine,
    ReceivedUnit,
    RefreshTokenRecord,
    StockLevel,
    StockMovement,
    Supplier,
    Tenant,
    User,
    UserAppRole,
    UserTenantAccess,
)
from domain.enums import (
    AcquisitionSource,
    AppRole,
    DocumentStatus,
    DocumentType,
    TenantRole,
    TenantStatus,
    TrackingType,
    TransactionType,
)
from domain.value_objects import Currency, Money


class FakeClock:
    def __init__(self, start: datetime | None = None) -> None:
        self.current = start or datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, delta: timedelta) -> None:
        self.current += delta


class FakeHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password_hash: str, password: str) -> bool:
        return password_hash == f"hashed:{password}"


class FakeTokenService:
    def issue_access(
        self,
        user_id: UUID,
        tenant_id: UUID | None,
        tenant_role: TenantRole | None,
        app_roles: Sequence[AppRole] = (),
    ) -> str:
        # Encodes the claims so tests can assert on what a token says.
        tenant = tenant_id or "none"
        role = tenant_role.value if tenant_role else "none"
        apps = "+".join(r.value for r in app_roles) or "none"
        return f"access:{user_id}:{tenant}:{role}:{apps}"

    def issue_refresh(self) -> RefreshTokenParts:
        secret = uuid4().hex
        return RefreshTokenParts(jti=uuid4(), secret=secret, token_hash=self.hash_opaque(secret))

    def new_opaque_secret(self) -> str:
        return uuid4().hex

    def hash_opaque(self, secret: str) -> str:
        return hashlib.sha256(secret.encode()).hexdigest()

    def parse_opaque(self, token: str) -> tuple[UUID, str] | None:
        id_part, sep, secret = token.partition(".")
        if not sep or not secret:
            return None
        try:
            return UUID(id_part), secret
        except ValueError:
            return None


class FakeRepository[EntityT: Entity[UUID]]:
    """The dict-backed half every fake repository shares.

    Mirrors ``CrudRepository``: ``get``/``add``/``update`` keyed by the
    identity the entity declares. Subclasses add only the finders their
    port declares beyond that.
    """

    def __init__(self) -> None:
        self.by_id: dict[UUID, EntityT] = {}

    async def get(self, key: UUID) -> EntityT | None:
        return self.by_id.get(key)

    async def add(self, entity: EntityT) -> None:
        self.by_id[entity.id] = entity

    async def update(self, entity: EntityT) -> None:
        self.by_id[entity.id] = entity


# --- MasterDB -------------------------------------------------------------


class FakeUserRepository(FakeRepository[User]):
    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.by_id.values() if u.email == email), None)


class FakeUserAppRoleRepository(FakeRepository[UserAppRole]):
    async def list_for_user(self, user_id: UUID) -> list[UserAppRole]:
        return [a for a in self.by_id.values() if a.user_id == user_id]


class FakeUserTenantAccessRepository(FakeRepository[UserTenantAccess]):
    async def list_for_user(self, user_id: UUID) -> list[UserTenantAccess]:
        return [g for g in self.by_id.values() if g.user_id == user_id]

    async def exists(self, user_id: UUID, tenant_id: UUID) -> bool:
        return any(
            g.user_id == user_id and g.tenant_id == tenant_id
            for g in self.by_id.values()
        )


class FakeTenantRepository(FakeRepository[Tenant]):
    async def get_by_slug(self, slug: str) -> Tenant | None:
        return next((t for t in self.by_id.values() if t.slug == slug), None)

    async def list_all(self) -> list[Tenant]:
        return sorted(self.by_id.values(), key=lambda t: t.created_at)


class FakeRefreshTokenRepository(FakeRepository[RefreshTokenRecord]):
    async def revoke_all_for_user(self, user_id: UUID, now: datetime) -> None:
        for record in self.by_id.values():
            if record.user_id == user_id and record.revoked_at is None:
                record.revoked_at = now


class FakeInvitationRepository(FakeRepository[Invitation]):
    """Plain CRUD, like the port it stands in for."""


# --- one tenant's database ------------------------------------------------


class FakeEmployeeRepository(FakeRepository[Employee]):
    async def get_by_email(self, email: str) -> Employee | None:
        return next((e for e in self.by_id.values() if e.email == email), None)

    async def list_all(self) -> list[Employee]:
        return sorted(self.by_id.values(), key=lambda e: e.created_at)

    async def count_owners(self) -> int:
        return sum(
            1 for e in self.by_id.values() if e.role is TenantRole.OWNER and e.is_active
        )


def _page[T](items: list[T], page: int, page_size: int) -> tuple[list[T], int]:
    """Same contract as ``CrudRepository._page``: the slice, and the
    unpaged total the caller needs to work out how many pages there are."""
    start = (page - 1) * page_size
    return items[start : start + page_size], len(items)


def _matches(term: str | None, *fields: str | None) -> bool:
    return term is None or any(f is not None and term.lower() in f.lower() for f in fields)


class FakeAppendOnlyRepository[EntityT: Entity[UUID]]:
    """The list-backed half every append-only fake shares.

    A list, not a dict: order of arrival *is* the data for a ledger, and
    there is no ``update`` because the port does not have one (§4.3 rule 2).
    """

    def __init__(self) -> None:
        self.rows: list[EntityT] = []

    async def add(self, entity: EntityT) -> None:
        self.rows.append(entity)


class FakeProductPriceChangeRepository(FakeAppendOnlyRepository[ProductPriceChange]):
    async def list_for_product(self, product_id: UUID) -> list[ProductPriceChange]:
        return [c for c in self.rows if c.product_id == product_id]

    async def latest_for_product(self, product_id: UUID) -> ProductPriceChange | None:
        found = await self.list_for_product(product_id)
        return found[-1] if found else None


class FakeDeviceUnitPriceChangeRepository(FakeAppendOnlyRepository[DeviceUnitPriceChange]):
    async def list_for_unit(self, device_unit_id: UUID) -> list[DeviceUnitPriceChange]:
        return [c for c in self.rows if c.device_unit_id == device_unit_id]

    async def latest_for_unit(self, device_unit_id: UUID) -> DeviceUnitPriceChange | None:
        found = await self.list_for_unit(device_unit_id)
        return found[-1] if found else None

    async def count_for_unit(self, device_unit_id: UUID) -> int:
        return len(await self.list_for_unit(device_unit_id))


class FakeDeviceUnitRepository(FakeRepository[DeviceUnit]):
    async def get_by_imei(self, imei: str) -> DeviceUnit | None:
        return next((u for u in self.by_id.values() if str(u.imei) == imei), None)

    async def list_by_ids(self, ids: Sequence[UUID]) -> list[DeviceUnit]:
        return [self.by_id[i] for i in ids if i in self.by_id]

    async def list_on_hand(self, location_id: UUID | None = None) -> list[DeviceUnit]:
        return [
            u
            for u in sorted(self.by_id.values(), key=lambda u: u.created_at)
            if u.status.is_on_hand
            and (location_id is None or u.location_id == location_id)
        ]


class FakeStockMovementRepository(FakeAppendOnlyRepository[StockMovement]):
    async def list_for_document(
        self, document_type: DocumentType, document_id: UUID
    ) -> list[StockMovement]:
        return [
            m
            for m in self.rows
            if m.document_type is document_type and m.document_id == document_id
        ]

    async def list_for_unit(self, device_unit_id: UUID) -> list[StockMovement]:
        return [m for m in self.rows if m.device_unit_id == device_unit_id]

    async def net_quantity(self, product_id: UUID, location_id: UUID) -> int:
        return sum(
            m.quantity_delta
            for m in self.rows
            if m.product_id == product_id and m.location_id == location_id
        )

    async def list_for_pair(
        self, product_id: UUID, location_id: UUID
    ) -> list[StockMovement]:
        return [
            m
            for m in self.rows
            if m.product_id == product_id
            and m.location_id == location_id
            and m.device_unit_id is None
        ]

    async def list_units_on_hand(self) -> list[UUID]:
        net: dict[UUID, int] = {}
        for m in self.rows:
            if m.device_unit_id is not None:
                net[m.device_unit_id] = net.get(m.device_unit_id, 0) + m.quantity_delta
        return [unit_id for unit_id, total in net.items() if total > 0]

    async def list_moved_pairs(self) -> list[tuple[UUID, UUID]]:
        return list(
            dict.fromkeys(
                (m.product_id, m.location_id)
                for m in self.rows
                if m.device_unit_id is None
            )
        )


class FakeFinancialTransactionRepository(FakeAppendOnlyRepository[FinancialTransaction]):
    async def list_for_document(
        self, document_type: DocumentType, document_id: UUID
    ) -> list[FinancialTransaction]:
        return [
            t
            for t in self.rows
            if t.document_type is document_type and t.document_id == document_id
        ]

    async def list_for_pair(
        self, product_id: UUID, location_id: UUID
    ) -> list[FinancialTransaction]:
        return [
            t
            for t in self.rows
            if t.product_id == product_id
            and t.location_id == location_id
            and t.device_unit_id is None
        ]

    async def totals_by_type(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[tuple[TransactionType, Currency], Money]:
        totals: dict[tuple[TransactionType, Currency], Money] = {}
        for txn in self.rows:
            if since is not None and txn.occurred_at < since:
                continue
            if until is not None and txn.occurred_at >= until:
                continue
            if location_id is not None and txn.location_id != location_id:
                continue
            key = (txn.txn_type, txn.currency)
            running = totals.get(key)
            totals[key] = txn.amount if running is None else running + txn.amount
        return totals


class FakeStockLevelRepository(FakeRepository[StockLevel]):
    async def get_for(self, product_id: UUID, location_id: UUID) -> StockLevel | None:
        return next(
            (
                level
                for level in self.by_id.values()
                if level.product_id == product_id and level.location_id == location_id
            ),
            None,
        )

    async def list_all(self) -> list[StockLevel]:
        return list(self.by_id.values())


class FakeProductRepository(FakeRepository[Product]):
    async def get_by_sku(self, sku: str) -> Product | None:
        return next((p for p in self.by_id.values() if str(p.sku) == sku), None)

    async def get_by_barcode(self, barcode: str) -> Product | None:
        return next(
            (p for p in self.by_id.values() if p.barcode and str(p.barcode) == barcode), None
        )

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
        tracking_type: TrackingType | None = None,
    ) -> tuple[list[Product], int]:
        found = [
            p
            for p in sorted(self.by_id.values(), key=lambda p: p.created_at)
            if _matches(search, str(p.sku), p.name, p.brand, str(p.barcode) if p.barcode else None)
            and (is_active is None or p.is_active is is_active)
            and (tracking_type is None or p.tracking_type is tracking_type)
        ]
        return _page(found, page, page_size)


class FakeLocationRepository(FakeRepository[Location]):
    async def get_by_name(self, name: str) -> Location | None:
        return next((loc for loc in self.by_id.values() if loc.name == name), None)

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Location], int]:
        found = [
            loc
            for loc in sorted(self.by_id.values(), key=lambda loc: loc.created_at)
            if _matches(search, loc.name)
            and (is_active is None or loc.is_active is is_active)
        ]
        return _page(found, page, page_size)


class FakeSupplierRepository(FakeRepository[Supplier]):
    async def get_by_name(self, name: str) -> Supplier | None:
        return next((s for s in self.by_id.values() if s.name == name), None)

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Supplier], int]:
        found = [
            s
            for s in sorted(self.by_id.values(), key=lambda s: s.created_at)
            if _matches(search, s.name, s.contact_name, s.phone)
            and (is_active is None or s.is_active is is_active)
        ]
        return _page(found, page, page_size)


class FakeCustomerRepository(FakeRepository[Customer]):
    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Customer], int]:
        found = [
            c
            for c in sorted(self.by_id.values(), key=lambda c: c.created_at)
            if _matches(search, c.full_name, c.phone)
            and (is_active is None or c.is_active is is_active)
        ]
        return _page(found, page, page_size)


class FakeTenantSettingsRepository:
    def __init__(self, timezone: str = "Asia/Tashkent") -> None:
        self.timezone = timezone

    async def get_timezone(self) -> str:
        return self.timezone

    async def set_timezone(self, timezone: str) -> None:
        self.timezone = timezone


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class FakeWorkspace:
    def __init__(self, employees: FakeEmployeeRepository, uow: FakeUnitOfWork) -> None:
        self.employees = employees
        self.uow = uow


class FakeTenantScope:
    """One employee repository per tenant id, created on first reach.

    Modelling several stores is what makes multi-tenant switching testable
    without a database.
    """

    def __init__(self, tenants: FakeTenantRepository) -> None:
        self._tenants = tenants
        self.stores: dict[UUID, FakeEmployeeRepository] = {}
        self.uows: dict[UUID, FakeUnitOfWork] = {}

    def employees_at(self, tenant_id: UUID) -> FakeEmployeeRepository:
        return self.stores.setdefault(tenant_id, FakeEmployeeRepository())

    @asynccontextmanager
    async def for_tenant(self, tenant_id: UUID) -> AsyncIterator[FakeWorkspace]:
        tenant = self._tenants.by_id.get(tenant_id)
        if tenant is not None and tenant.status is not TenantStatus.ACTIVE:
            raise TenantNotActiveError()
        uow = self.uows.setdefault(tenant_id, FakeUnitOfWork())
        yield FakeWorkspace(self.employees_at(tenant_id), uow)


class FakeProvisioner:
    """Flips the tenant to ACTIVE like the real one, or fails on demand.

    Also seeds the Owner's ``Employee`` into that store — keyed by the
    master user id, as the real provisioner does.
    """

    def __init__(
        self,
        tenants: FakeTenantRepository,
        scope: FakeTenantScope,
        clock: FakeClock,
        fail: bool = False,
    ) -> None:
        self._tenants = tenants
        self._scope = scope
        self._clock = clock
        self.fail = fail
        self.calls: list[tuple[UUID, str, OwnerSeed | None]] = []

    async def provision(
        self, tenant_id: UUID, timezone: str, owner: OwnerSeed | None = None
    ) -> None:
        self.calls.append((tenant_id, timezone, owner))
        tenant = self._tenants.by_id[tenant_id]
        if self.fail:
            tenant.status = TenantStatus.FAILED
            raise ProvisioningFailedError(str(tenant_id))
        if owner is not None:
            self._scope.employees_at(tenant_id).by_id[owner.user_id] = Employee(
                id=owner.user_id,
                email=owner.email,
                full_name=owner.full_name,
                role=TenantRole.OWNER,
                is_active=True,
                created_at=self._clock.now(),
            )
        tenant.status = TenantStatus.ACTIVE


# --- M4 inbound documents (PRD §4.4, §5.3) -------------------------------


class FakeDocumentNumberRepository:
    """One counter per (document type, year), as the locked row is."""

    def __init__(self) -> None:
        self.counters: dict[tuple[DocumentType, int], int] = {}

    async def next_number(self, document_type: DocumentType, year: int) -> int:
        key = (document_type, year)
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]


class FakePurchaseOrderRepository(FakeRepository[PurchaseOrder]):
    async def update_line(self, line: PurchaseOrderLine) -> None:
        return None

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        status: DocumentStatus | None = None,
        supplier_id: UUID | None = None,
    ) -> tuple[list[PurchaseOrder], int]:
        found = [
            order
            for order in self.by_id.values()
            if _matches(search, order.number)
            and (status is None or order.status is status)
            and (supplier_id is None or order.supplier_id == supplier_id)
        ]
        return _page(sorted(found, key=lambda o: o.created_at, reverse=True), page, page_size)


class FakeGoodsReceiptRepository(FakeRepository[GoodsReceipt]):
    """The scan methods write through the aggregate the handler already
    holds, exactly as the SQL repository writes one row rather than
    rewriting a fifty-line receipt per beep."""

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        status: DocumentStatus | None = None,
        acquisition_source: AcquisitionSource | None = None,
    ) -> tuple[list[GoodsReceipt], int]:
        found = [
            receipt
            for receipt in self.by_id.values()
            if _matches(search, receipt.number)
            and (status is None or receipt.status is status)
            and (
                acquisition_source is None
                or receipt.acquisition_source is acquisition_source
            )
        ]
        return _page(sorted(found, key=lambda r: r.created_at, reverse=True), page, page_size)

    async def add_unit(self, unit: ReceivedUnit) -> None:
        return None

    async def update_unit(self, unit: ReceivedUnit) -> None:
        return None

    async def remove_unit(self, unit_id: UUID) -> None:
        return None

    async def received_quantities(self, purchase_order_id: UUID) -> dict[UUID, int]:
        """Confirmed receipts only — a draft has received nothing (FR-3.9)."""
        received: dict[UUID, int] = {}
        for receipt in self.by_id.values():
            if (
                receipt.purchase_order_id != purchase_order_id
                or receipt.status is not DocumentStatus.CONFIRMED
            ):
                continue
            for product_id, quantity in receipt.received_quantities().items():
                received[product_id] = received.get(product_id, 0) + quantity
        return received
