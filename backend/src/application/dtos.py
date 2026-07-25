"""Application DTOs — frozen dataclasses crossing the use-case boundary.

They carry data and validate nothing (PRD §7.3): structural validation
happens in presentation schemas, semantic validation in the domain.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.roles import AppRole, TenantRole


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """The authenticated identity extracted from a validated access token.

    ``tenant_id``/``tenant_role`` are None for a platform operator, whose
    token carries no tenant claim. ``permissions`` is the resolved union of
    everything their app and tenant roles allow — authorization compares
    against this, never against a role name (PRD §2.1).
    """

    user_id: UUID
    permissions: frozenset[str]
    tenant_id: UUID | None = None
    tenant_role: TenantRole | None = None
    app_roles: tuple[AppRole, ...] = ()

    @property
    def is_platform_operator(self) -> bool:
        return bool(self.app_roles)


@dataclass(frozen=True, slots=True)
class RequestedTenant:
    """The store an ``X-Tenant`` header asked for, if any (PRD §3.3).

    Resolved from a slug or a UUID at the edge, but *not* authorized there:
    on the anonymous auth routes there is no identity yet to authorize
    against. ``ClaimsFactory`` makes that check once the user is known.
    """

    tenant_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AuthTokens:
    access_token: str
    refresh_token: str


@dataclass(frozen=True, slots=True)
class RefreshTokenParts:
    """A freshly generated refresh token, before persistence.

    The wire format is ``"{jti}.{secret}"``; only ``token_hash`` is stored.
    """

    jti: UUID
    secret: str
    token_hash: str


@dataclass(frozen=True, slots=True)
class IssuedClaims:
    """What the claims factory resolved for one token issuance.

    The port of ``UserCustomClaimsFactory``'s output: which store this token
    speaks for, and with what role there.
    """

    tenant_id: UUID | None
    tenant_role: TenantRole | None
    app_roles: tuple[AppRole, ...]


@dataclass(frozen=True, slots=True)
class OwnerSeed:
    """The Owner's ``Employee`` row that provisioning writes into a new store.

    ``user_id`` is the master ``User.id`` and becomes ``Employee.id`` — the
    equality the ledger's foreign keys depend on from M3.
    """

    user_id: UUID
    email: str
    full_name: str


@dataclass(frozen=True, slots=True)
class CreateTenantCommand:
    name: str
    slug: str
    owner_email: str
    owner_full_name: str
    timezone: str


@dataclass(frozen=True, slots=True)
class CreateTenantResult:
    """The temporary password exists only here — it is never stored in plaintext."""

    tenant_id: UUID
    slug: str
    owner_email: str
    owner_user_id: UUID
    temporary_password: str


@dataclass(frozen=True, slots=True)
class LoginResult:
    """``tenant_id`` is None for a platform operator, who has no home store."""

    tokens: AuthTokens
    must_change_password: bool
    tenant_id: UUID | None = None
    tenant_role: TenantRole | None = None
    app_roles: tuple[AppRole, ...] = ()


@dataclass(frozen=True, slots=True)
class InviteEmployeeCommand:
    """No ``tenant_id``: the store is the one the request resolved to, and
    ``InviteUser`` holds it — so the store checked for a duplicate and the
    store written onto the invitation cannot drift apart."""

    email: str
    role: TenantRole
    invited_by: UUID


@dataclass(frozen=True, slots=True)
class InviteResult:
    invitation_id: UUID
    token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AcceptInviteCommand:
    token: str
    password: str | None
    full_name: str | None


@dataclass(frozen=True, slots=True)
class AcceptInviteResult:
    user_id: UUID
    tenant_id: UUID | None


@dataclass(frozen=True, slots=True)
class MeView:
    user_id: UUID
    email: str
    full_name: str
    must_change_password: bool
    permissions: frozenset[str] = field(default_factory=frozenset)
    tenant_id: UUID | None = None
    tenant_role: TenantRole | None = None
    app_roles: tuple[AppRole, ...] = ()
