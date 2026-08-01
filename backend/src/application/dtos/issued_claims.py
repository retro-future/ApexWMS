"""What the claims factory resolved for one token issuance."""

from dataclasses import dataclass
from uuid import UUID

from domain.enums import AppRole, TenantRole


@dataclass(frozen=True, slots=True)
class IssuedClaims:
    """What the claims factory resolved for one token issuance.

    The port of ``UserCustomClaimsFactory``'s output: which store this token
    speaks for, and with what role there.
    """

    tenant_id: UUID | None
    tenant_role: TenantRole | None
    app_roles: tuple[AppRole, ...]
