"""Security ports: password hashing and token issuance."""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from application.dtos import RefreshTokenParts
from domain.enums import AppRole, TenantRole


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool:
        """True iff the password matches; never raises on mismatch."""
        ...


class TokenService(Protocol):
    def issue_access(
        self,
        user_id: UUID,
        tenant_id: UUID | None,
        tenant_role: TenantRole | None,
        app_roles: Sequence[AppRole] = (),
    ) -> str:
        """A signed access token carrying at most one tenant_id (FR-1.3).

        ``tenant_id`` and ``tenant_role`` are None together, for a platform
        operator who belongs to no store — such a token carries no tenant
        claim at all rather than a null one.
        """
        ...

    def issue_refresh(self) -> RefreshTokenParts: ...

    def new_opaque_secret(self) -> str:
        """A high-entropy secret for single-use links (invitations)."""
        ...

    def hash_opaque(self, secret: str) -> str:
        """Deterministic hash for storing/looking up opaque secrets."""
        ...

    def parse_opaque(self, token: str) -> tuple[UUID, str] | None:
        """Split an opaque ``"{id}.{secret}"`` token; ``None`` if malformed.

        Callers decide which application error a malformed token means —
        a bad refresh token and a bad invitation token are different
        failures even though they share this wire format.
        """
        ...
