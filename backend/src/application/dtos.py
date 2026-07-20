"""Application DTOs — frozen dataclasses crossing the use-case boundary.

They carry data and validate nothing (PRD §7.3): structural validation
happens in presentation schemas, semantic validation in the domain.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.entities import User
from domain.roles import Role


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """The authenticated identity extracted from a validated access token."""

    user_id: UUID
    tenant_id: UUID
    role: Role


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
class SignUpCommand:
    tenant_name: str
    email: str
    password: str
    full_name: str
    timezone: str


@dataclass(frozen=True, slots=True)
class SignUpResult:
    tenant_id: UUID
    tokens: AuthTokens


@dataclass(frozen=True, slots=True)
class TenantChoice:
    """One of several tenants a multi-tenant user may log into (FR-1.3)."""

    tenant_id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class LoginResult:
    """Either issued tokens, or the tenant list to choose from (FR-1.3)."""

    tokens: AuthTokens | None
    tenant_id: UUID | None
    role: Role | None
    tenant_choices: list[TenantChoice] | None


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
class UserWithRole:
    user: User
    role: Role


@dataclass(frozen=True, slots=True)
class MeView:
    user_id: UUID
    email: str
    full_name: str
    tenant_id: UUID
    role: Role
