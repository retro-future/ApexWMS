"""TenantDB repository ports (PRD §3.1).

No method takes a ``tenant_id``: the session these are bound to *is* the
tenant, so there is no filter to forget.

``list_page`` returns ``(items, total)`` rather than just the page,
because ``PagedResult.succeed_with_data`` needs the unpaged count to work
out how many pages there are. Filtering lives in the repository — a
handler that fetched everything and sliced in Python would read the whole
catalog on every request.
"""

from typing import Protocol
from uuid import UUID

from application.ports.repository import Repository
from domain.entities import Customer, Employee, Location, Product, Supplier
from domain.enums import TrackingType


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
