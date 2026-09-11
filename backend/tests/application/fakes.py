"""In-memory fakes for the application ports (PRD §9 Testing:
use cases are tested with no database at all).

The split mirrors the real one: ``FakeUserRepository`` and friends stand
for MasterDB, ``FakeEmployeeRepository`` for one store's database, and
``FakeTenantScope`` for reaching a store the edge did not resolve.
"""

from __future__ import annotations

import hashlib
import operator
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.sql.operators import in_op

from application.dtos import (
    CreditInvoiceDebt,
    DebtorSummary,
    FinancingSplitRow,
    InventoryValueRow,
    Letterhead,
    OwnerSeed,
    PriceDeviation,
    RefreshTokenParts,
    SalesTotalsRow,
    SettledSale,
    TenantLogo,
    TradeInPayout,
    UnitOrigin,
    UnitSale,
)
from application.errors import ProvisioningFailedError, TenantNotActiveError
from application.sorting import DeviationSort
from application.specs import (
    ActiveOwners,
    CreditCompanyBrowse,
    CustomerBrowse,
    CustomerForWrite,
    CustomerReturnBrowse,
    CustomerReturnById,
    CustomerReturnForWrite,
    CustomerReturnsForInvoice,
    DeviceUnitById,
    DeviceUnitByImei,
    DeviceUnitForWrite,
    DeviceUnitsByIds,
    GoodsReceiptBrowse,
    GoodsReceiptById,
    GoodsReceiptForWrite,
    InvitationForWrite,
    LiveTokensForUser,
    LocationBrowse,
    OnHandDeviceUnits,
    ProductBarcodeTakenByAnother,
    ProductBrowse,
    ProductByBarcode,
    ProductBySku,
    ProductForWrite,
    PurchaseOrderBrowse,
    PurchaseOrderById,
    PurchaseOrderForWrite,
    RefreshTokenForWrite,
    SalesInvoiceBrowse,
    SalesInvoiceById,
    SalesInvoiceForWrite,
    StockCountBrowse,
    StockCountById,
    StockCountForWrite,
    SupplierForWrite,
    SupplierReturnBrowse,
    SupplierReturnById,
    SupplierReturnForWrite,
    WriteOffBrowse,
    WriteOffById,
    WriteOffForWrite,
)
from domain.core import Entity
from domain.entities import (
    CreditCompany,
    Customer,
    CustomerReturn,
    DeviceUnit,
    DeviceUnitPriceChange,
    Employee,
    ExchangeRate,
    FinancialTransaction,
    GoodsReceipt,
    Invitation,
    Location,
    Payment,
    Product,
    ProductPriceChange,
    PurchaseOrder,
    RefreshTokenRecord,
    SalesInvoice,
    StockCount,
    StockLevel,
    StockMovement,
    Supplier,
    SupplierReturn,
    Tenant,
    User,
    UserAppRole,
    UserTenantAccess,
    WriteOff,
)
from domain.enums import (
    AcquisitionSource,
    AppRole,
    CatalogCodeKind,
    DocumentStatus,
    DocumentType,
    MovementType,
    PaymentType,
    TenantRole,
    TenantStatus,
    TransactionType,
)
from domain.value_objects import Currency, Money


def _spec_matches(entity: object, spec: object) -> bool:
    """Evaluate an inline ``Specification``'s equality criteria against an
    entity the way SQL would against a row.

    Only ``==`` / ``!=`` / ``IN`` over a plain column are handled — the
    probe specs that stay classes are the ones whose value is an enum or a
    value object, and the fakes for those read the class attributes instead.
    """
    for crit in spec.criteria:  # type: ignore[attr-defined]
        actual = getattr(entity, crit.left.key)
        want = crit.right.value
        op = crit.operator
        if op is operator.eq and actual != want:
            return False
        if op is operator.ne and actual == want:
            return False
        if op is in_op and actual not in want:
            return False
    return True


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

    async def update(self, entity: EntityT, spec: object | None = None) -> None:
        self.by_id[entity.id] = entity

    async def find_one(self, spec: object) -> EntityT | None:
        return next((e for e in self.by_id.values() if _spec_matches(e, spec)), None)

    async def exists(self, spec: object) -> bool:
        return any(_spec_matches(e, spec) for e in self.by_id.values())


# --- MasterDB -------------------------------------------------------------


class FakeUserRepository(FakeRepository[User]):
    """Spec-based, like the SQL repository. ``find_one``/``exists`` come from
    the base: ``UserForWrite`` and an inline ``email ==`` probe are both
    plain equality criteria."""


class FakeUserAppRoleRepository(FakeRepository[UserAppRole]):
    async def find(self, spec: object) -> list[UserAppRole]:
        return [a for a in self.by_id.values() if _spec_matches(a, spec)]


class FakeUserTenantAccessRepository(FakeRepository[UserTenantAccess]):
    async def find(self, spec: object) -> list[UserTenantAccess]:
        return [g for g in self.by_id.values() if _spec_matches(g, spec)]


class FakeTenantRepository(FakeRepository[Tenant]):
    """``find_one``/``exists`` from the base: ``TenantForWrite`` and an
    inline ``slug ==`` probe are plain equality criteria."""


class FakeRefreshTokenRepository(FakeRepository[RefreshTokenRecord]):
    async def find_one(
        self, spec: RefreshTokenForWrite
    ) -> RefreshTokenRecord | None:
        return self.by_id.get(spec.token_id)

    async def find(self, spec: LiveTokensForUser) -> list[RefreshTokenRecord]:
        return [
            r
            for r in self.by_id.values()
            if r.user_id == spec.user_id and r.revoked_at is None
        ]


class FakeInvitationRepository(FakeRepository[Invitation]):
    async def find_one(
        self, spec: InvitationForWrite
    ) -> Invitation | None:
        return self.by_id.get(spec.invitation_id)


# --- one tenant's database ------------------------------------------------


class FakeEmployeeRepository(FakeRepository[Employee]):
    """Spec-based, like the SQL repository. ``find_one``/``exists`` come from
    the base (``EmployeeForWrite``, inline ``email ==`` probe)."""

    async def find(self, spec: object) -> list[Employee]:
        return sorted(self.by_id.values(), key=lambda e: e.created_at)

    async def count(self, spec: ActiveOwners) -> int:
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
    """Spec-based. Rows are held in arrival order, which is time order, so
    ``find_one`` (``LatestPriceChangeForProduct``) is the last match."""

    async def find(self, spec: object) -> list[ProductPriceChange]:
        return [c for c in self.rows if _spec_matches(c, spec)]

    async def find_one(self, spec: object) -> ProductPriceChange | None:
        found = [c for c in self.rows if _spec_matches(c, spec)]
        return found[-1] if found else None


class FakeDeviceUnitPriceChangeRepository(FakeAppendOnlyRepository[DeviceUnitPriceChange]):
    """Spec-based. Arrival order is time order, so ``find_one``
    (``LatestPriceChangeForUnit``) is the last match."""

    async def find(self, spec: object) -> list[DeviceUnitPriceChange]:
        return [c for c in self.rows if _spec_matches(c, spec)]

    async def find_one(self, spec: object) -> DeviceUnitPriceChange | None:
        found = [c for c in self.rows if _spec_matches(c, spec)]
        return found[-1] if found else None


class FakeDeviceUnitRepository(FakeRepository[DeviceUnit]):
    """Spec-based, like the SQL repository."""

    async def find_one(
        self, spec: DeviceUnitById | DeviceUnitForWrite | DeviceUnitByImei
    ) -> DeviceUnit | None:
        if isinstance(spec, DeviceUnitByImei):
            return next(
                (u for u in self.by_id.values() if str(u.imei) == spec.imei), None
            )
        return self.by_id.get(spec.device_unit_id)

    async def exists(self, spec: DeviceUnitById) -> bool:
        return spec.device_unit_id in self.by_id

    async def find(
        self, spec: DeviceUnitsByIds | OnHandDeviceUnits
    ) -> list[DeviceUnit]:
        if isinstance(spec, DeviceUnitsByIds):
            return [self.by_id[i] for i in spec.ids if i in self.by_id]
        return [
            u
            for u in sorted(self.by_id.values(), key=lambda u: u.created_at)
            if u.status.is_on_hand
            and (spec.location_id is None or u.location_id == spec.location_id)
        ]


class FakeStockMovementRepository(FakeAppendOnlyRepository[StockMovement]):
    """Spec-based. The movement specs carry their filters as plain
    attributes; no SQLAlchemy criteria are read."""

    async def find(self, spec: object) -> list[StockMovement]:
        return sorted(
            (m for m in self.rows if _movement_matches(m, spec)),
            key=lambda m: m.occurred_at,
        )


def _movement_matches(movement: StockMovement, spec: object) -> bool:
    doc_type = getattr(spec, "document_type", None)
    if doc_type is not None and movement.document_type is not doc_type:
        return False
    if hasattr(spec, "document_id") and movement.document_id != spec.document_id:  # type: ignore[attr-defined]
        return False
    if hasattr(spec, "device_unit_id") and movement.device_unit_id != spec.device_unit_id:  # type: ignore[attr-defined]
        return False
    if hasattr(spec, "product_id"):
        if movement.product_id != spec.product_id or movement.location_id != spec.location_id:  # type: ignore[attr-defined]
            return False
        if movement.device_unit_id is not None:  # MovementsForPair is quantity-only
            return False
        if not _before(movement.occurred_at, spec):
            return False
    return True


def _before(occurred_at: datetime, spec: object) -> bool:
    """``MovementsForPair``/``TransactionsForPair``'s optional cutoff, exclusive."""
    as_of = getattr(spec, "as_of", None)
    return as_of is None or occurred_at < as_of


class FakeStockMovementQueries:
    """Reads the movements the fake repository holds, folded the way
    ``SqlStockMovementQueries`` folds its rows."""

    def __init__(
        self,
        movements: FakeStockMovementRepository,
        units: FakeDeviceUnitRepository | None = None,
    ) -> None:
        self._rows = movements.rows
        # Only the as-of valuation needs the units; the older reads do not,
        # and the World builds this fake for both.
        self._units = units

    async def net_quantity(self, product_id: UUID, location_id: UUID) -> int:
        return sum(
            m.quantity_delta
            for m in self._rows
            if m.product_id == product_id and m.location_id == location_id
        )

    async def units_on_hand(self) -> list[UUID]:
        net: dict[UUID, int] = {}
        for m in self._rows:
            if m.device_unit_id is not None:
                net[m.device_unit_id] = net.get(m.device_unit_id, 0) + m.quantity_delta
        return [unit_id for unit_id, total in net.items() if total > 0]

    async def moved_pairs(self, as_of: datetime | None = None) -> list[tuple[UUID, UUID]]:
        return list(
            dict.fromkeys(
                (m.product_id, m.location_id)
                for m in self._rows
                if m.device_unit_id is None
                and (as_of is None or m.occurred_at < as_of)
            )
        )

    async def serialized_value_at(
        self, as_of: datetime, location_id: UUID | None = None
    ) -> list[InventoryValueRow]:
        """Two passes over the cutoff, like the SQL: what is still held, and
        where each unit's last movement left it."""
        assert self._units is not None
        net: dict[UUID, int] = {}
        placed: dict[UUID, UUID] = {}
        for m in sorted(self._rows, key=lambda one: (one.occurred_at, one.id)):
            if m.device_unit_id is None or m.occurred_at >= as_of:
                continue
            net[m.device_unit_id] = net.get(m.device_unit_id, 0) + m.quantity_delta
            placed[m.device_unit_id] = m.location_id

        held: dict[tuple[UUID, Currency], tuple[int, Money]] = {}
        for unit_id, total in net.items():
            unit = self._units.by_id.get(unit_id)
            if total <= 0 or unit is None:
                continue
            place = placed[unit_id]
            if location_id is not None and place != location_id:
                continue
            key = (place, unit.acquisition_cost.currency)
            quantity, value = held.get(
                key, (0, Money.zero(unit.acquisition_cost.currency))
            )
            held[key] = (quantity + 1, value + unit.acquisition_cost)

        return [
            InventoryValueRow(
                location_id=place,
                location_name=None,
                quantity=quantity,
                amount=value,
            )
            for (place, _), (quantity, value) in sorted(
                held.items(), key=lambda pair: (str(pair[0][0]), pair[0][1].value)
            )
        ]

    async def units_sold(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[UUID, int]:
        sold: dict[UUID, int] = {}
        for m in self._rows:
            if m.movement_type is not MovementType.SALE:
                continue
            if from_date is not None and m.occurred_at < from_date:
                continue
            if to_date is not None and m.occurred_at > to_date:
                continue
            if location_id is not None and m.location_id != location_id:
                continue
            sold[m.location_id] = sold.get(m.location_id, 0) - m.quantity_delta
        return sold


class FakeFinancialTransactionRepository(FakeAppendOnlyRepository[FinancialTransaction]):
    """Spec-based. The transaction specs carry their filters as plain
    attributes; no SQLAlchemy criteria are read."""

    async def find(self, spec: object) -> list[FinancialTransaction]:
        return sorted(
            (t for t in self.rows if _txn_matches(t, spec)),
            key=lambda t: t.occurred_at,
        )


def _txn_matches(txn: FinancialTransaction, spec: object) -> bool:
    doc_type = getattr(spec, "document_type", None)
    if doc_type is not None and txn.document_type is not doc_type:
        return False
    if hasattr(spec, "document_id") and txn.document_id != spec.document_id:  # type: ignore[attr-defined]
        return False
    if hasattr(spec, "product_id"):
        if txn.product_id != spec.product_id or txn.location_id != spec.location_id:  # type: ignore[attr-defined]
            return False
        if txn.device_unit_id is not None:  # TransactionsForPair is quantity-only
            return False
        if not _before(txn.occurred_at, spec):
            return False
    return True


class FakeFinancialTransactionQueries:
    """The money-ledger aggregates the fake repository holds."""

    def __init__(
        self,
        transactions: FakeFinancialTransactionRepository,
        locations: FakeLocationRepository | None = None,
    ) -> None:
        self._rows = transactions.rows
        self._locations = locations

    async def totals_by_type(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[tuple[TransactionType, Currency], Money]:
        totals: dict[tuple[TransactionType, Currency], Money] = {}
        for txn in self._rows:
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

    async def totals_by_type_and_day(
        self,
        *,
        timezone: str,
        since: datetime | None = None,
        until: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[tuple[TransactionType, Currency, date], Money]:
        zone = ZoneInfo(timezone)
        totals: dict[tuple[TransactionType, Currency, date], Money] = {}
        for txn in self._rows:
            if since is not None and txn.occurred_at < since:
                continue
            if until is not None and txn.occurred_at >= until:
                continue
            if location_id is not None and txn.location_id != location_id:
                continue
            key = (txn.txn_type, txn.currency, txn.occurred_at.astimezone(zone).date())
            running = totals.get(key)
            totals[key] = txn.amount if running is None else running + txn.amount
        return totals

    async def sales_totals(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        location_id: UUID | None = None,
    ) -> list[SalesTotalsRow]:
        wanted = {
            TransactionType.SALE_REVENUE,
            TransactionType.COGS,
            TransactionType.SALES_RETURN_REFUND,
        }
        buckets: dict[tuple[UUID | None, TransactionType, Currency], Money] = {}
        for txn in self._rows:
            if txn.txn_type not in wanted:
                continue
            if from_date is not None and txn.occurred_at < from_date:
                continue
            if to_date is not None and txn.occurred_at > to_date:
                continue
            if location_id is not None and txn.location_id != location_id:
                continue
            key = (txn.location_id, txn.txn_type, txn.currency)
            running = buckets.get(key)
            buckets[key] = txn.amount if running is None else running + txn.amount

        def name_of(place: UUID | None) -> str | None:
            if place is None or self._locations is None:
                return None
            found = self._locations.by_id.get(place)
            return found.name if found is not None else None

        return [
            SalesTotalsRow(
                location_id=place,
                location_name=name_of(place),
                txn_type=txn_type,
                amount=amount,
            )
            for (place, txn_type, _currency), amount in buckets.items()
        ]


class FakeStockLevelRepository(FakeRepository[StockLevel]):
    """Spec-based, like the SQL repository. ``find_one`` (the pair probe)
    comes from the base; ``find`` sorts by product for the count snapshot."""

    async def find(self, spec: object) -> list[StockLevel]:
        return sorted(
            (lv for lv in self.by_id.values() if _spec_matches(lv, spec)),
            key=lambda lv: str(lv.product_id),
        )


class FakeProductRepository(FakeRepository[Product]):
    """Spec-based, like the SQL repository. ``ProductBySku``/``ProductByBarcode``
    are read back through ``find_one`` and used as probes through ``exists``;
    ``ProductBrowse`` carries its filters as plain attributes."""

    async def find_one(
        self, spec: ProductForWrite | ProductBySku | ProductByBarcode
    ) -> Product | None:
        if isinstance(spec, ProductBySku):
            return next(
                (p for p in self.by_id.values() if str(p.sku) == spec.sku), None
            )
        if isinstance(spec, ProductByBarcode):
            return next(
                (
                    p
                    for p in self.by_id.values()
                    if p.barcode and str(p.barcode) == spec.barcode
                ),
                None,
            )
        return self.by_id.get(spec.product_id)

    async def exists(
        self,
        spec: ProductBySku | ProductByBarcode | ProductBarcodeTakenByAnother,
    ) -> bool:
        if isinstance(spec, ProductBySku):
            return any(str(p.sku) == spec.sku for p in self.by_id.values())
        return any(
            p.barcode
            and str(p.barcode) == spec.barcode
            and p.id != getattr(spec, "exclude_id", None)
            for p in self.by_id.values()
        )

    async def find(self, spec: ProductBrowse) -> list[Product]:
        found = self._filter(spec)
        if spec.offset is not None:
            found = found[spec.offset :]
        if spec.limit is not None:
            found = found[: spec.limit]
        return found

    async def count(self, spec: ProductBrowse) -> int:
        return len(self._filter(spec))

    def _filter(self, spec: ProductBrowse) -> list[Product]:
        return [
            p
            for p in sorted(self.by_id.values(), key=lambda p: p.created_at)
            if _matches(
                spec.search,
                str(p.sku),
                p.name,
                p.brand,
                str(p.barcode) if p.barcode else None,
            )
            and (spec.is_active is None or p.is_active is spec.is_active)
            and (spec.tracking_type is None or p.tracking_type is spec.tracking_type)
        ]


class FakeLocationRepository(FakeRepository[Location]):
    """Spec-based, like the SQL repository. ``find_one``/``exists`` come from
    the base (``LocationForWrite``, inline ``name ==`` probes);
    ``LocationBrowse`` carries its filters as plain attributes."""

    async def find(self, spec: LocationBrowse) -> list[Location]:
        found = self._filter(spec)
        if spec.offset is not None:
            found = found[spec.offset :]
        if spec.limit is not None:
            found = found[: spec.limit]
        return found

    async def count(self, spec: LocationBrowse) -> int:
        return len(self._filter(spec))

    def _filter(self, spec: LocationBrowse) -> list[Location]:
        return [
            loc
            for loc in sorted(self.by_id.values(), key=lambda loc: loc.created_at)
            if _matches(spec.search, loc.name)
            and (spec.is_active is None or loc.is_active is spec.is_active)
        ]


class FakeSupplierRepository(FakeRepository[Supplier]):
    """A stand-in for the *other* aggregates' tests, not the supplier ones.

    Suppliers moved to the specification-based repository, and the handler
    tests that actually exercise their reads moved to Postgres with them
    (``tests/api/test_catalog_api.py``). What is left here is the one thing
    a purchase order, a goods receipt or a return asks of a supplier: load
    it by id (``repo.get``) for the name on the PDF, or to check the id is
    one of ours. Nothing else is supported on purpose.
    """

    async def find_one(self, spec: SupplierForWrite) -> Supplier | None:
        return self.by_id.get(spec.supplier_id)


class FakeCustomerRepository(FakeRepository[Customer]):
    """Spec-based, like the SQL repository. ``CustomerBrowse`` carries its
    filters as plain attributes; no SQLAlchemy criteria are read."""

    async def find_one(self, spec: CustomerForWrite) -> Customer | None:
        return self.by_id.get(spec.customer_id)

    async def find(self, spec: CustomerBrowse) -> list[Customer]:
        found = self._filter(spec)
        if spec.offset is not None:
            found = found[spec.offset :]
        if spec.limit is not None:
            found = found[: spec.limit]
        return found

    async def count(self, spec: CustomerBrowse) -> int:
        return len(self._filter(spec))

    def _filter(self, spec: CustomerBrowse) -> list[Customer]:
        return [
            c
            for c in sorted(self.by_id.values(), key=lambda c: c.created_at)
            if _matches(spec.search, c.full_name, c.phone)
            and (spec.is_active is None or c.is_active is spec.is_active)
        ]


class FakeSalesInvoiceRepository(FakeRepository[SalesInvoice]):
    """Spec-based. Scanning and unscanning mutate ``invoice.lines`` on the
    aggregate the handler holds, and ``update`` re-stores that same object,
    so no per-line method is needed."""

    async def find_one(
        self, spec: SalesInvoiceById | SalesInvoiceForWrite
    ) -> SalesInvoice | None:
        return self.by_id.get(spec.sales_invoice_id)

    async def find(self, spec: SalesInvoiceBrowse) -> list[SalesInvoice]:
        found = self._filter(spec)
        found.sort(key=lambda i: i.created_at, reverse=True)
        if spec.offset is not None:
            found = found[spec.offset :]
        if spec.limit is not None:
            found = found[: spec.limit]
        return found

    async def count(self, spec: SalesInvoiceBrowse) -> int:
        return len(self._filter(spec))

    def _filter(self, spec: SalesInvoiceBrowse) -> list[SalesInvoice]:
        return [
            invoice
            for invoice in self.by_id.values()
            if _matches(spec.search, invoice.number)
            and (spec.status is None or invoice.status is spec.status)
            and (spec.customer_id is None or invoice.customer_id == spec.customer_id)
            and (spec.location_id is None or invoice.location_id == spec.location_id)
        ]


class FakeSalesInvoiceQueries:
    """Reads the invoice aggregates the fake repository holds, folded the
    way ``SqlSalesInvoiceQueries`` folds its joined rows. Needs the payment
    and customer-return fakes too, since a balance is
    ``debt − payments − relief`` and the SQL reads join all three tables;
    ``World`` wires it after they are built."""

    def __init__(
        self,
        invoices: FakeSalesInvoiceRepository,
        payments: FakePaymentRepository,
        returns: FakeCustomerReturnRepository,
    ) -> None:
        self._invoices = invoices
        self._payments = payments
        self._returns = returns

    @property
    def _by_id(self) -> dict[UUID, SalesInvoice]:
        return self._invoices.by_id

    async def credit_history_for(self, customer_id: UUID) -> list[CreditInvoiceDebt]:
        found = [
            self._to_debt(invoice)
            for invoice in self._by_id.values()
            if invoice.customer_id == customer_id
            and invoice.payment_type is not PaymentType.PAID_IN_FULL
            and invoice.status is not DocumentStatus.DRAFT
        ]
        return sorted(
            found, key=lambda d: d.confirmed_at or datetime.min.replace(tzinfo=UTC), reverse=True
        )

    async def sales_of_unit(self, device_unit_id: UUID) -> dict[UUID, UnitSale]:
        sold: dict[UUID, UnitSale] = {}
        for invoice in self._by_id.values():
            if invoice.status is DocumentStatus.DRAFT:
                continue
            for line in invoice.lines:
                if line.device_unit_id != device_unit_id:
                    continue
                sold[invoice.id] = UnitSale(
                    invoice_id=invoice.id,
                    invoice_number=invoice.number,
                    customer_id=invoice.customer_id,
                    customer_name=None,
                    resolved_price=line.resolved_price,
                    charged_price=line.charged_price,
                    price_approved_by=line.price_approved_by,
                    price_approved_by_name=None,
                    price_note=line.price_note,
                )
        return sold

    async def list_deviations(
        self,
        page: int,
        page_size: int,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        approved_by: UUID | None = None,
        customer_id: UUID | None = None,
        sort: DeviationSort = DeviationSort.CONFIRMED_AT,
    ) -> tuple[list[PriceDeviation], int]:
        found: list[PriceDeviation] = []
        for invoice in self._by_id.values():
            if invoice.status is not DocumentStatus.CONFIRMED:
                continue
            if customer_id is not None and invoice.customer_id != customer_id:
                continue
            for line in invoice.deviations():
                if approved_by is not None and line.price_approved_by != approved_by:
                    continue
                assert line.resolved_price is not None
                assert line.charged_price is not None
                assert invoice.confirmed_at is not None
                found.append(
                    PriceDeviation(
                        invoice_id=invoice.id,
                        invoice_number=invoice.number,
                        confirmed_at=invoice.confirmed_at,
                        customer_id=invoice.customer_id,
                        customer_name=None,
                        product_id=line.product_id,
                        product_name=str(line.product_id),
                        imei=None,
                        resolved_price=line.resolved_price,
                        charged_price=line.charged_price,
                        price_approved_by=line.price_approved_by,
                        price_approved_by_name=None,
                        price_note=line.price_note,
                    )
                )
        found.sort(
            key=lambda d: d.confirmed_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return _page(found, page, page_size)

    async def list_debtors(
        self, page: int, page_size: int
    ) -> tuple[list[DebtorSummary], int]:
        by_customer: dict[UUID, list[CreditInvoiceDebt]] = {}
        for invoice in self._by_id.values():
            if invoice.customer_id is None or not invoice.payment_type.opens_debt:
                continue
            if invoice.status is not DocumentStatus.CONFIRMED:
                continue
            by_customer.setdefault(invoice.customer_id, []).append(self._to_debt(invoice))

        summaries: list[DebtorSummary] = []
        for customer_id, debts in by_customer.items():
            open_debts = [debt for debt in debts if debt.is_open]
            if not open_debts:
                continue
            balance = Money.zero(Currency.UZS)
            for debt in open_debts:
                balance = balance + debt.remaining
            summaries.append(
                DebtorSummary(
                    customer_id=customer_id,
                    full_name=str(customer_id),
                    phone=None,
                    balance=balance,
                    oldest_open_at=min(
                        debt.confirmed_at
                        for debt in open_debts
                        if debt.confirmed_at is not None
                    ),
                    open_invoice_count=len(open_debts),
                )
            )
        return _page(sorted(summaries, key=lambda s: s.oldest_open_at), page, page_size)

    async def total_debt(self) -> Money:
        total = Money.zero(Currency.UZS)
        for invoice in self._by_id.values():
            if invoice.status is not DocumentStatus.CONFIRMED:
                continue
            if not invoice.payment_type.opens_debt or invoice.debt is None:
                continue
            total = (
                total
                + invoice.debt
                - self._paid(invoice.id)
                - self._relieved(invoice.id)
            )
        return total

    def _to_debt(self, invoice: SalesInvoice) -> CreditInvoiceDebt:
        return CreditInvoiceDebt(
            invoice_id=invoice.id,
            invoice_number=invoice.number,
            status=invoice.status,
            payment_type=invoice.payment_type,
            confirmed_at=invoice.confirmed_at,
            debt=invoice.debt,
            paid=self._paid(invoice.id),
            relieved=self._relieved(invoice.id),
            credit_company_id=invoice.credit_company_id,
            contract_ref=invoice.contract_ref,
        )

    def _paid(self, invoice_id: UUID) -> Money:
        """The debt reads join ``sales_invoices`` and ``payments``, so this
        fake reads the payment fake alongside its own invoices."""
        total = Money.zero(Currency.UZS)
        for payment in self._payments.rows:
            if payment.sales_invoice_id == invoice_id:
                total = total + payment.amount
        return total

    def _relieved(self, invoice_id: UUID) -> Money:
        """Som written off by confirmed customer returns (FR-4.9d)."""
        total = Money.zero(Currency.UZS)
        for document in self._returns.by_id.values():
            if document.sales_invoice_id != invoice_id:
                continue
            if document.status is not DocumentStatus.CONFIRMED:
                continue
            if document.debt_relief is not None:
                total = total + document.debt_relief
        return total


class FakeMonthEndQueries:
    """The period reads behind the close, folded from the same aggregates
    ``SqlMonthEndQueries`` reads out of three tables."""

    def __init__(
        self,
        invoices: FakeSalesInvoiceRepository,
        payments: FakePaymentRepository,
        companies: FakeCreditCompanyRepository,
        transactions: FakeFinancialTransactionRepository,
        returns: FakeCustomerReturnRepository,
        receipts: FakeGoodsReceiptRepository,
    ) -> None:
        self._invoices = invoices
        self._payments = payments
        self._companies = companies
        self._transactions = transactions
        self._returns = returns
        self._receipts = receipts

    async def debt_at(self, as_of: datetime) -> Money:
        total = Money.zero(Currency.UZS)
        for invoice in self._invoices.by_id.values():
            if not self._open_debt_at(invoice, as_of) or invoice.debt is None:
                continue
            total = (
                total
                + invoice.debt
                - self._paid(invoice.id, as_of)
                - self._relieved(invoice.id, as_of)
            )
        return total

    async def debt_booked_between(self, since: datetime, until: datetime) -> Money:
        total = Money.zero(Currency.UZS)
        for invoice in self._invoices.by_id.values():
            if invoice.payment_type is not PaymentType.STORE_CREDIT:
                continue
            if invoice.confirmed_at is None or not since <= invoice.confirmed_at < until:
                continue
            total = total + (invoice.debt or Money.zero(Currency.UZS))
        return total

    async def debt_voided_between(self, since: datetime, until: datetime) -> Money:
        total = Money.zero(Currency.UZS)
        for invoice in self._invoices.by_id.values():
            if invoice.payment_type is not PaymentType.STORE_CREDIT:
                continue
            if invoice.cancelled_at is None or not since <= invoice.cancelled_at < until:
                continue
            total = (
                total
                + (invoice.debt or Money.zero(Currency.UZS))
                - self._paid(invoice.id)
                - self._relieved(invoice.id)
            )
        return total

    async def debt_relieved_between(self, since: datetime, until: datetime) -> Money:
        total = Money.zero(Currency.UZS)
        for document in self._returns.by_id.values():
            if document.debt_relief is None or document.confirmed_at is None:
                continue
            if not since <= document.confirmed_at < until:
                continue
            invoice = self._invoices.by_id.get(document.sales_invoice_id)
            if invoice is None or invoice.payment_type is not PaymentType.STORE_CREDIT:
                continue
            if invoice.cancelled_at is not None and invoice.cancelled_at < until:
                continue
            total = total + document.debt_relief
        return total

    def _relieved(self, invoice_id: UUID, as_of: datetime | None = None) -> Money:
        total = Money.zero(Currency.UZS)
        for document in self._returns.by_id.values():
            if document.sales_invoice_id != invoice_id:
                continue
            if document.debt_relief is None or document.confirmed_at is None:
                continue
            if as_of is not None and document.confirmed_at >= as_of:
                continue
            total = total + document.debt_relief
        return total

    async def sales_by_financing(
        self,
        since: datetime,
        until: datetime,
        location_id: UUID | None = None,
    ) -> list[FinancingSplitRow]:
        counted: dict[tuple[PaymentType, UUID | None, Currency], tuple[set[UUID], Money]] = {}
        for txn in self._transactions.rows:
            if txn.txn_type is not TransactionType.SALE_REVENUE:
                continue
            if txn.document_type is not DocumentType.SALES_INVOICE:
                continue
            if not since <= txn.occurred_at < until:
                continue
            if location_id is not None and txn.location_id != location_id:
                continue
            invoice = self._invoices.by_id.get(txn.document_id)
            if invoice is None:
                continue
            key = (invoice.payment_type, invoice.credit_company_id, txn.currency)
            seen, revenue = counted.get(key, (set(), Money.zero(txn.currency)))
            seen.add(invoice.id)
            counted[key] = (seen, revenue + txn.amount)

        return [
            FinancingSplitRow(
                payment_type=payment_type,
                credit_company_id=company_id,
                credit_company_name=self._company_name(company_id),
                invoice_count=len(seen),
                revenue=revenue,
            )
            for (payment_type, company_id, _), (seen, revenue) in sorted(
                counted.items(), key=lambda pair: (pair[0][0].value, str(pair[0][1]))
            )
        ]

    async def settled_sales(
        self,
        *,
        timezone: str,
        since: datetime,
        until: datetime,
        location_id: UUID | None = None,
    ) -> list[SettledSale]:
        zone = ZoneInfo(timezone)
        settled: list[SettledSale] = []
        for invoice in self._invoices.by_id.values():
            if invoice.confirmed_at is None or invoice.cancelled_at is not None:
                continue
            if not since <= invoice.confirmed_at < until:
                continue
            if location_id is not None and invoice.location_id != location_id:
                continue
            on_credit = invoice.payment_type is PaymentType.STORE_CREDIT
            if on_credit:
                # A payment against the debt is that same debt arriving.
                received = [invoice.debt] if invoice.debt else []
            else:
                received = [
                    payment.amount
                    for payment in self._payments.rows
                    if payment.sales_invoice_id == invoice.id
                ]
            settled.append(
                SettledSale(
                    day=invoice.confirmed_at.astimezone(zone).date(),
                    charged=tuple(invoice.subtotals().values()),
                    received=tuple(received),
                    on_credit=on_credit,
                )
            )
        return settled

    async def trade_in_payouts(
        self,
        *,
        timezone: str,
        since: datetime,
        until: datetime,
        location_id: UUID | None = None,
    ) -> list[TradeInPayout]:
        zone = ZoneInfo(timezone)
        payouts: list[TradeInPayout] = []
        for receipt in self._receipts.by_id.values():
            if receipt.acquisition_source is not AcquisitionSource.TRADE_IN:
                continue
            if receipt.confirmed_at is None or receipt.cancelled_at is not None:
                continue
            if not since <= receipt.confirmed_at < until:
                continue
            if location_id is not None and receipt.location_id != location_id:
                continue
            units = list(receipt.units())
            payouts.append(
                TradeInPayout(
                    day=receipt.confirmed_at.astimezone(zone).date(),
                    valued=tuple(
                        unit.acquisition_cost
                        for unit in units
                        if unit.acquisition_cost is not None
                    ),
                    paid=tuple(
                        Money(unit.cash_paid_minor, unit.cash_paid_currency)
                        for unit in units
                        if unit.cash_paid_minor is not None
                        and unit.cash_paid_currency is not None
                    ),
                )
            )
        return payouts

    @staticmethod
    def _open_debt_at(invoice: SalesInvoice, as_of: datetime) -> bool:
        return (
            invoice.payment_type is PaymentType.STORE_CREDIT
            and invoice.confirmed_at is not None
            and invoice.confirmed_at < as_of
            and (invoice.cancelled_at is None or invoice.cancelled_at >= as_of)
        )

    def _company_name(self, company_id: UUID | None) -> str | None:
        if company_id is None:
            return None
        company = self._companies.by_id.get(company_id)
        return None if company is None else company.name

    def _paid(self, invoice_id: UUID, as_of: datetime | None = None) -> Money:
        total = Money.zero(Currency.UZS)
        for payment in self._payments.rows:
            if payment.sales_invoice_id != invoice_id:
                continue
            if as_of is not None and payment.occurred_at >= as_of:
                continue
            total = total + payment.amount
        return total


class FakeCreditCompanyRepository(FakeRepository[CreditCompany]):
    """Spec-based, like the SQL repository. ``find_one``/``exists`` come from
    the base (``CreditCompanyForWrite``, inline ``name ==`` probes);
    ``CreditCompanyBrowse`` carries its filters as plain attributes."""

    async def find(self, spec: CreditCompanyBrowse) -> list[CreditCompany]:
        found = self._filter(spec)
        if spec.offset is not None:
            found = found[spec.offset :]
        if spec.limit is not None:
            found = found[: spec.limit]
        return found

    async def count(self, spec: CreditCompanyBrowse) -> int:
        return len(self._filter(spec))

    def _filter(self, spec: CreditCompanyBrowse) -> list[CreditCompany]:
        return [
            company
            for company in sorted(self.by_id.values(), key=lambda c: c.created_at)
            if _matches(spec.search, company.name, company.contact_name, company.phone)
            and (spec.is_active is None or company.is_active == spec.is_active)
        ]


class FakePaymentRepository(FakeAppendOnlyRepository[Payment]):
    """Spec-based, plus ``get`` by id (the append-only port carries it)."""

    async def get(self, payment_id: UUID) -> Payment | None:
        return next((p for p in self.rows if p.id == payment_id), None)

    async def find(self, spec: object) -> list[Payment]:
        return sorted(
            (p for p in self.rows if _spec_matches(p, spec)),
            key=lambda p: p.occurred_at,
        )

    async def find_one(self, spec: object) -> Payment | None:
        return next((p for p in self.rows if _spec_matches(p, spec)), None)


class FakeExchangeRateRepository(FakeAppendOnlyRepository[ExchangeRate]):
    """Spec-based, plus ``get`` by id. Arrival order is quote order, so
    ``find_one`` (``LatestRateFor``) is the last match."""

    async def get(self, rate_id: UUID) -> ExchangeRate | None:
        return next((r for r in self.rows if r.id == rate_id), None)

    async def find(self, spec: object) -> list[ExchangeRate]:
        return [r for r in self.rows if _spec_matches(r, spec)]

    async def find_one(self, spec: object) -> ExchangeRate | None:
        found = [r for r in self.rows if _spec_matches(r, spec)]
        return found[-1] if found else None

    async def count(self, spec: object) -> int:
        return len([r for r in self.rows if _spec_matches(r, spec)])


class FakeTenantSettingsRepository:
    def __init__(self, timezone: str = "Asia/Tashkent", *, till: bool = False) -> None:
        self.timezone = timezone
        self.letterhead = Letterhead()
        # Off by default, like a real store: the till is opt-in (§4.5b).
        self.till = till

    async def get_timezone(self) -> str:
        return self.timezone

    async def set_timezone(self, timezone: str) -> None:
        self.timezone = timezone

    async def get_letterhead(self) -> Letterhead:
        return self.letterhead

    async def set_letterhead(self, letterhead: Letterhead) -> None:
        # Text only, mirroring the real repository: the logo has its own
        # setter so a settings write cannot drop one.
        self.letterhead = replace(
            self.letterhead,
            business_name=letterhead.business_name,
            address=letterhead.address,
        )

    async def set_logo(self, logo: TenantLogo | None) -> None:
        self.letterhead = replace(self.letterhead, logo=logo)

    async def runs_till(self) -> bool:
        return self.till

    async def set_runs_till(self, runs_till: bool) -> None:
        self.till = runs_till


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


class FakeDocumentNumberAllocator:
    """One counter per (document type, year), as the locked row is."""

    def __init__(self) -> None:
        self.counters: dict[tuple[DocumentType, int], int] = {}

    async def next_number(self, document_type: DocumentType, year: int) -> int:
        key = (document_type, year)
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]


class FakeCatalogCodeAllocator:
    """One counter per kind, as the locked row is."""

    def __init__(self) -> None:
        self.counters: dict[CatalogCodeKind, int] = {}

    async def next(self, kind: CatalogCodeKind) -> int:
        self.counters[kind] = self.counters.get(kind, 0) + 1
        return self.counters[kind]


class FakePurchaseOrderRepository(FakeRepository[PurchaseOrder]):
    """Spec-based, like the SQL repository. ``find_one`` reads the id off
    the spec; ``find``/``count`` read ``PurchaseOrderBrowse``'s plain
    filter attributes. No SQLAlchemy criteria are evaluated."""

    async def find_one(
        self, spec: PurchaseOrderById | PurchaseOrderForWrite
    ) -> PurchaseOrder | None:
        return self.by_id.get(spec.purchase_order_id)

    async def find(self, spec: PurchaseOrderBrowse) -> list[PurchaseOrder]:
        found = self._filter(spec)
        found.sort(key=lambda o: o.created_at, reverse=True)
        if spec.offset is not None:
            found = found[spec.offset :]
        if spec.limit is not None:
            found = found[: spec.limit]
        return found

    async def count(self, spec: PurchaseOrderBrowse) -> int:
        return len(self._filter(spec))

    def _filter(self, spec: PurchaseOrderBrowse) -> list[PurchaseOrder]:
        return [
            order
            for order in self.by_id.values()
            if _matches(spec.search, order.number)
            and (spec.status is None or order.status is spec.status)
            and (spec.supplier_id is None or order.supplier_id == spec.supplier_id)
        ]


class FakeGoodsReceiptRepository(FakeRepository[GoodsReceipt]):
    """Spec-based. Scanning, pricing and unscanning mutate ``receipt.lines``
    on the aggregate the handler holds, and ``update`` re-stores that same
    object, so no per-unit method is needed."""

    async def find_one(
        self, spec: GoodsReceiptById | GoodsReceiptForWrite
    ) -> GoodsReceipt | None:
        return self.by_id.get(spec.goods_receipt_id)

    async def find(self, spec: GoodsReceiptBrowse) -> list[GoodsReceipt]:
        found = self._filter(spec)
        found.sort(key=lambda r: r.created_at, reverse=True)
        if spec.offset is not None:
            found = found[spec.offset :]
        if spec.limit is not None:
            found = found[: spec.limit]
        return found

    async def count(self, spec: GoodsReceiptBrowse) -> int:
        return len(self._filter(spec))

    def _filter(self, spec: GoodsReceiptBrowse) -> list[GoodsReceipt]:
        return [
            receipt
            for receipt in self.by_id.values()
            if _matches(spec.search, receipt.number)
            and (spec.status is None or receipt.status is spec.status)
            and (
                spec.acquisition_source is None
                or receipt.acquisition_source is spec.acquisition_source
            )
        ]


class FakeGoodsReceiptQueries:
    """Reads the receipt aggregates the fake repository holds, folded the way
    ``SqlGoodsReceiptQueries`` folds its joined rows."""

    def __init__(self, receipts: FakeGoodsReceiptRepository) -> None:
        self._receipts = receipts

    async def received_quantities(self, purchase_order_id: UUID) -> dict[UUID, int]:
        """Confirmed receipts only — a draft has received nothing (FR-3.9)."""
        received: dict[UUID, int] = {}
        for receipt in self._receipts.by_id.values():
            if (
                receipt.purchase_order_id != purchase_order_id
                or receipt.status is not DocumentStatus.CONFIRMED
            ):
                continue
            for product_id, quantity in receipt.received_quantities().items():
                received[product_id] = received.get(product_id, 0) + quantity
        return received

    async def supplier_of(self, receipt_id: UUID) -> UUID | None:
        receipt = self._receipts.by_id.get(receipt_id)
        return None if receipt is None else receipt.supplier_id

    async def origin_of(self, receipt_id: UUID) -> UnitOrigin | None:
        receipt = self._receipts.by_id.get(receipt_id)
        if receipt is None:
            return None
        return UnitOrigin(
            acquisition_source=receipt.acquisition_source,
            supplier_id=receipt.supplier_id,
            supplier_name=None,
            customer_id=receipt.customer_id,
            customer_name=None,
        )


class FakeSupplierReturnRepository(FakeRepository[SupplierReturn]):
    """Spec-based. Scanning mutates ``document.lines`` on the aggregate the
    handler holds, and ``update`` re-stores that same object, so no line
    method is needed."""

    async def find_one(
        self, spec: SupplierReturnById | SupplierReturnForWrite
    ) -> SupplierReturn | None:
        return self.by_id.get(spec.supplier_return_id)

    async def find(self, spec: SupplierReturnBrowse) -> list[SupplierReturn]:
        found = self._filter(spec)
        found.sort(key=lambda d: d.created_at, reverse=True)
        if spec.offset is not None:
            found = found[spec.offset :]
        if spec.limit is not None:
            found = found[: spec.limit]
        return found

    async def count(self, spec: SupplierReturnBrowse) -> int:
        return len(self._filter(spec))

    def _filter(self, spec: SupplierReturnBrowse) -> list[SupplierReturn]:
        return [
            document
            for document in self.by_id.values()
            if _matches(spec.search, document.number)
            and (spec.status is None or document.status is spec.status)
            and (spec.supplier_id is None or document.supplier_id == spec.supplier_id)
            and (spec.reason is None or document.reason is spec.reason)
        ]


class FakeCustomerReturnRepository(FakeRepository[CustomerReturn]):
    """Spec-based, the same shape as the supplier return's.

    ``CustomerReturnsForInvoice`` is the extra one: the double-return guard
    and every balance read ask "what has come back against this sale".
    """

    async def find_one(
        self, spec: CustomerReturnById | CustomerReturnForWrite
    ) -> CustomerReturn | None:
        return self.by_id.get(spec.customer_return_id)

    async def find(
        self, spec: CustomerReturnBrowse | CustomerReturnsForInvoice
    ) -> list[CustomerReturn]:
        if isinstance(spec, CustomerReturnsForInvoice):
            return [
                document
                for document in self.by_id.values()
                if document.sales_invoice_id == spec.sales_invoice_id
            ]
        found = self._filter(spec)
        found.sort(key=lambda d: d.created_at, reverse=True)
        if spec.offset is not None:
            found = found[spec.offset :]
        if spec.limit is not None:
            found = found[: spec.limit]
        return found

    async def count(self, spec: CustomerReturnBrowse) -> int:
        return len(self._filter(spec))

    def _filter(self, spec: CustomerReturnBrowse) -> list[CustomerReturn]:
        return [
            document
            for document in self.by_id.values()
            if _matches(spec.search, document.number)
            and (spec.status is None or document.status is spec.status)
            and (spec.customer_id is None or document.customer_id == spec.customer_id)
            and (spec.location_id is None or document.location_id == spec.location_id)
            and (spec.reason is None or document.reason is spec.reason)
        ]


class FakeWriteOffRepository(FakeRepository[WriteOff]):
    """Spec-based. Scanning mutates ``document.lines`` on the aggregate the
    handler holds, and ``update`` re-stores that same object."""

    async def find_one(
        self, spec: WriteOffById | WriteOffForWrite
    ) -> WriteOff | None:
        return self.by_id.get(spec.write_off_id)

    async def find(self, spec: WriteOffBrowse) -> list[WriteOff]:
        found = self._filter(spec)
        found.sort(key=lambda d: d.created_at, reverse=True)
        if spec.offset is not None:
            found = found[spec.offset :]
        if spec.limit is not None:
            found = found[: spec.limit]
        return found

    async def count(self, spec: WriteOffBrowse) -> int:
        return len(self._filter(spec))

    def _filter(self, spec: WriteOffBrowse) -> list[WriteOff]:
        return [
            document
            for document in self.by_id.values()
            if _matches(spec.search, document.number)
            and (spec.status is None or document.status is spec.status)
            and (spec.location_id is None or document.location_id == spec.location_id)
            and (spec.reason is None or document.reason is spec.reason)
        ]


class FakeStockCountRepository(FakeRepository[StockCount]):
    """Spec-based. Scanning and counting mutate the aggregate the handler
    holds, and ``update`` re-stores that same object."""

    async def find_one(
        self, spec: StockCountById | StockCountForWrite
    ) -> StockCount | None:
        return self.by_id.get(spec.stock_count_id)

    async def find(self, spec: StockCountBrowse) -> list[StockCount]:
        found = self._filter(spec)
        found.sort(key=lambda c: c.created_at, reverse=True)
        if spec.offset is not None:
            found = found[spec.offset :]
        if spec.limit is not None:
            found = found[: spec.limit]
        return found

    async def count(self, spec: StockCountBrowse) -> int:
        return len(self._filter(spec))

    def _filter(self, spec: StockCountBrowse) -> list[StockCount]:
        return [
            count
            for count in self.by_id.values()
            if _matches(spec.search, count.number)
            and (spec.status is None or count.status is spec.status)
            and (spec.location_id is None or count.location_id == spec.location_id)
        ]
