"""TenantDB repository ports (PRD §3.1).

No method takes a ``tenant_id``: the session these are bound to *is* the
tenant, so there is no filter to forget. Business aggregates arrive with M2.
"""

from typing import Protocol
from uuid import UUID

from application.ports.repository import Repository
from domain.entities import Employee


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
