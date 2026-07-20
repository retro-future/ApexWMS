"""Security ports: password hashing and token issuance."""

from typing import Protocol
from uuid import UUID

from application.dtos import RefreshTokenParts
from domain.roles import Role


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool:
        """True iff the password matches; never raises on mismatch."""
        ...


class TokenService(Protocol):
    def issue_access(self, user_id: UUID, tenant_id: UUID, role: Role) -> str:
        """A signed access token carrying exactly one tenant_id (FR-1.3)."""
        ...

    def issue_refresh(self) -> RefreshTokenParts: ...

    def new_opaque_secret(self) -> str:
        """A high-entropy secret for single-use links (invitations)."""
        ...

    def hash_opaque(self, secret: str) -> str:
        """Deterministic hash for storing/looking up opaque secrets."""
        ...
