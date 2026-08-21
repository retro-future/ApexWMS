"""TenantDB repository ports (PRD §3.1).

No method takes a ``tenant_id``: the session these are bound to *is* the
tenant, so there is no filter to forget.

``list_page`` returns ``(items, total)`` rather than just the page,
because ``PagedResult.succeed_with_data`` needs the unpaged count to work
out how many pages there are. Filtering lives in the repository — a
handler that fetched everything and sliced in Python would read the whole
catalog on every request.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from application.dtos import Letterhead, PriceDeviation
from application.ports.repository import AppendOnlyRepository, Repository
from domain.entities import (
    Customer,
    DeviceUnit,
    DeviceUnitPriceChange,
    Employee,
    FinancialTransaction,
    GoodsReceipt,
    Location,
    Product,
    ProductPriceChange,
    PurchaseOrder,
    PurchaseOrderLine,
    ReceivedUnit,
    SalesInvoice,
    SalesInvoiceLine,
    StockLevel,
    StockMovement,
    Supplier,
)
from domain.enums import (
    AcquisitionSource,
    DocumentStatus,
    DocumentType,
    TrackingType,
    TransactionType,
)
from domain.value_objects import Currency, Money


class EmployeeRepository(Repository[Employee, UUID], Protocol):
    """Keyed by the master ``User.id`` — see ``domain.entities.employee``."""

    async def get_by_email(self, email: str) -> Employee | None: ...

    async def list_all(self) -> list[Employee]:
        """Everyone who works at this store, oldest first."""
        ...

    async def count_owners(self) -> int:
        """Guards against demoting the last Owner and locking the store out."""
        ...


class TenantSettingsRepository(Protocol):
    """The singleton settings row seeded at provisioning — not aggregate CRUD."""

    async def get_timezone(self) -> str: ...

    async def set_timezone(self, timezone: str) -> None: ...

    async def get_letterhead(self) -> Letterhead:
        """The store's own details, for the top of a printed document (FR-8.1)."""
        ...

    async def set_letterhead(self, letterhead: Letterhead) -> None: ...


class ProductRepository(Repository[Product, UUID], Protocol):
    async def get_by_sku(self, sku: str) -> Product | None: ...

    async def get_by_barcode(self, barcode: str) -> Product | None: ...

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
        tracking_type: TrackingType | None = None,
    ) -> tuple[list[Product], int]:
        """One page of the catalog, oldest first, plus the unpaged total.

        *search* matches SKU, name, brand or barcode, case-insensitively.
        """
        ...


class ProductPriceChangeRepository(AppendOnlyRepository[ProductPriceChange], Protocol):
    """The catalog-price log (FR-2.19). Append and read; never update."""

    async def list_for_product(self, product_id: UUID) -> list[ProductPriceChange]:
        """One product's whole history, oldest first (FR-9.2b)."""
        ...

    async def latest_for_product(self, product_id: UUID) -> ProductPriceChange | None:
        """The row ``Product.default_sale_price`` is the projection of."""
        ...


class LocationRepository(Repository[Location, UUID], Protocol):
    async def get_by_name(self, name: str) -> Location | None: ...

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Location], int]: ...


class SupplierRepository(Repository[Supplier, UUID], Protocol):
    async def get_by_name(self, name: str) -> Supplier | None: ...

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Supplier], int]: ...


class CustomerRepository(Repository[Customer, UUID], Protocol):
    """Customers are not name-unique: people share names (PRD §4.2)."""

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Customer], int]:
        """*search* matches name or phone."""
        ...


# --- M3 ledgers (PRD §4.3, §4.6) -----------------------------------------


class DeviceUnitRepository(Repository[DeviceUnit, UUID], Protocol):
    """Handsets. ``update`` exists, but the three fields it writes —
    status, location, asking price — are projections: only a ledger
    posting or the repricer may move them (§4.3 rule 1, FR-2.15)."""

    async def get_by_imei(self, imei: str) -> DeviceUnit | None:
        """FR-3.5/FR-7.1: what the scanner asks."""
        ...

    async def list_by_ids(self, ids: Sequence[UUID]) -> list[DeviceUnit]:
        """Bulk repricing's read (FR-2.21) — the call is atomic, so every
        unit must be in hand before any of them is priced."""
        ...

    async def list_on_hand(self, location_id: UUID | None = None) -> list[DeviceUnit]:
        """Everything the store still physically holds (§4.6, FR-9.1)."""
        ...


class DeviceUnitPriceChangeRepository(AppendOnlyRepository[DeviceUnitPriceChange], Protocol):
    """A handset's markdown log (FR-2.15). Append and read; never update."""

    async def list_for_unit(self, device_unit_id: UUID) -> list[DeviceUnitPriceChange]: ...

    async def latest_for_unit(
        self, device_unit_id: UUID
    ) -> DeviceUnitPriceChange | None:
        """The row ``DeviceUnit.asking_price`` is the projection of."""
        ...

    async def count_for_unit(self, device_unit_id: UUID) -> int:
        """How many times this handset has been marked down (FR-9.4)."""
        ...


class StockMovementRepository(AppendOnlyRepository[StockMovement], Protocol):
    """The stock ledger (§4.3) — immutable, and the source every stock
    projection is rebuildable from."""

    async def list_for_document(
        self, document_type: DocumentType, document_id: UUID
    ) -> list[StockMovement]:
        """Everything one document wrote — what a cancellation compensates."""
        ...

    async def list_for_unit(self, device_unit_id: UUID) -> list[StockMovement]:
        """One handset's whole life, in order — the IMEI trace (FR-9.2)."""
        ...

    async def net_quantity(self, product_id: UUID, location_id: UUID) -> int:
        """What the ledger says the level should be — the truth half of
        ``verify-projections``."""
        ...

    async def list_for_pair(
        self, product_id: UUID, location_id: UUID
    ) -> list[StockMovement]:
        """One quantity product's movements at one location, in order.

        The sequence a weighted-average cost pool is replayed from
        (§4.6) — order matters, because the average at the time of each
        sale is what its COGS used.
        """
        ...

    async def list_moved_pairs(self) -> list[tuple[UUID, UUID]]:
        """Every (product, location) the ledger has touched, so the sweep
        is driven off the ledger and catches a level never written at all."""
        ...

    async def list_units_on_hand(self) -> list[UUID]:
        """Every handset the ledger says is still in stock.

        The counterpart to ``DeviceUnitRepository.list_on_hand``; auditing
        needs both ends, or a unit silently marked ``SOLD`` is never looked
        at again.
        """
        ...


class FinancialTransactionRepository(AppendOnlyRepository[FinancialTransaction], Protocol):
    """The money ledger (§4.6). Every aggregate is per currency."""

    async def list_for_document(
        self, document_type: DocumentType, document_id: UUID
    ) -> list[FinancialTransaction]:
        """Everything one document booked — what a cancellation reverses."""
        ...

    async def totals_by_type(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[tuple[TransactionType, Currency], Money]:
        """Each category's net, keyed by (category, currency) — because no
        total spans both, and *until* is exclusive so a period is
        ``[start, next start)`` (FR-10.8)."""
        ...

    async def list_for_pair(
        self, product_id: UUID, location_id: UUID
    ) -> list[FinancialTransaction]:
        """What one product cost at one location, in order.

        Paired with the movements of the same product and location, this
        is what a cost pool is replayed from: the quantities come from the
        stock ledger and the money from this one, so a COGS booked at the
        wrong average shows up as a disagreement between them.
        """
        ...


class StockLevelRepository(Repository[StockLevel, UUID], Protocol):
    """The quantity projection (§4.2), written only by a ledger posting."""

    async def get_for(self, product_id: UUID, location_id: UUID) -> StockLevel | None: ...

    async def list_all(self) -> list[StockLevel]: ...


# --- M4 documents (PRD §4.4, §5.3) ---------------------------------------


class DocumentNumberRepository(Protocol):
    """The per-tenant sequence behind ``PO-2026-0001`` (§4.4).

    Not a repository of entities: one counter per (document type, year),
    handed out under a row lock so two operators filling in receipts at the
    same counter cannot be given the same number.
    """

    async def next_number(self, document_type: DocumentType, year: int) -> int: ...


class PurchaseOrderRepository(Repository[PurchaseOrder, UUID], Protocol):
    """An order and its lines, loaded and saved as one aggregate (§4.4)."""

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        status: DocumentStatus | None = None,
        supplier_id: UUID | None = None,
    ) -> tuple[list[PurchaseOrder], int]:
        """*search* matches the document number."""
        ...

    async def update_line(self, line: PurchaseOrderLine) -> None:
        """Price one line while the order is still a draft (FR-3.1)."""
        ...


class GoodsReceiptRepository(Repository[GoodsReceipt, UUID], Protocol):
    """A receipt, its lines and every IMEI scanned onto it (§4.4).

    ``add_unit``/``remove_unit`` exist because a scan is one row and
    rewriting the whole aggregate per beep would not hold §6's 200ms.
    """

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        status: DocumentStatus | None = None,
        acquisition_source: AcquisitionSource | None = None,
    ) -> tuple[list[GoodsReceipt], int]: ...

    async def add_unit(self, unit: ReceivedUnit) -> None: ...

    async def update_unit(self, unit: ReceivedUnit) -> None:
        """Price one already-scanned handset (FR-3.4b)."""
        ...

    async def remove_unit(self, unit_id: UUID) -> None:
        """Undo a scan while the receipt is still a draft (FR-3.12)."""
        ...

    async def received_quantities(self, purchase_order_id: UUID) -> dict[UUID, int]:
        """Product → quantity received against this order, confirmed receipts
        only. FR-3.9's pending/partial/complete is this against what was
        ordered; a draft receipt has received nothing."""
        ...


class SalesInvoiceRepository(Repository[SalesInvoice, UUID], Protocol):
    """An invoice and the lines scanned onto it (§4.4, §5.4).

    ``add_line``/``remove_line`` exist for the same reason the receipt's
    unit methods do: a scan is one row, and §6 gives the round trip 200ms.
    """

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        status: DocumentStatus | None = None,
        customer_id: UUID | None = None,
        location_id: UUID | None = None,
    ) -> tuple[list[SalesInvoice], int]: ...

    async def add_line(self, line: SalesInvoiceLine) -> None: ...

    async def update_line(self, line: SalesInvoiceLine) -> None:
        """Override one line's price, or fix its snapshot at confirm (FR-4.5)."""
        ...

    async def remove_line(self, line_id: UUID) -> None:
        """Take a line off while the invoice is still a draft (FR-4.5c)."""
        ...

    async def list_deviations(
        self,
        page: int,
        page_size: int,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        approved_by: UUID | None = None,
        customer_id: UUID | None = None,
    ) -> tuple[list[PriceDeviation], int]:
        """FR-9.7: confirmed lines charged something other than the resolved
        price, newest first.

        Confirmed only. A cancelled invoice keeps its snapshots, but a
        reversed sale is not a deviation anyone still has to answer for.
        """
        ...
