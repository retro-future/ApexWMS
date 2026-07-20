"""TenantDB repository ports (M1: settings only; business aggregates arrive with M2)."""

from typing import Protocol


class TenantSettingsRepository(Protocol):
    """The singleton settings row seeded at provisioning — not aggregate CRUD."""

    async def get_timezone(self) -> str: ...

    async def set_timezone(self, timezone: str) -> None: ...
