"""Application-internal DTOs — frozen dataclasses that never cross an HTTP
boundary: DI-context values (``CurrentUser``, ``RequestedTenant``) and
carriers passed between collaborator services (``ClaimsFactory``,
``TokenIssuer``). CQRS messages — commands, queries, and their result
payloads — are Pydantic models instead, defined alongside their handler in
``application/commands/``/``application/queries/`` (see ``application/core/``
for the shared base classes). The split is by role, not by layer: does this
object cross a message boundary that needs structural validation and JSON
shape, or does it just carry context through the DI graph?
"""

from dataclasses import dataclass
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


