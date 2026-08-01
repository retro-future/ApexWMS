"""The authenticated identity extracted from a validated access token."""

from dataclasses import dataclass
from uuid import UUID

from domain.enums import AppRole, TenantRole
from domain.permissions import Permission


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """The authenticated identity extracted from a validated access token.

    ``tenant_id``/``tenant_role`` are None for a platform operator, whose
    token carries no tenant claim. ``permissions`` is the resolved union of
    everything their app and tenant roles allow — authorization compares
    against this, never against a role name (PRD §2.1).
    """

    user_id: UUID
    permissions: frozenset[Permission]
    tenant_id: UUID | None = None
    tenant_role: TenantRole | None = None
    app_roles: tuple[AppRole, ...] = ()

    @property
    def is_platform_operator(self) -> bool:
        return bool(self.app_roles)
