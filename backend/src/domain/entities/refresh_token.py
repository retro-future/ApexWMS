"""A stored refresh token (FR-1.2): rotated on use, revocable.

Only the sha256 hash of the secret is stored. ``replaced_by`` links the
rotation chain; presenting an already-revoked token is treated as theft
and revokes every live token for that user+tenant.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.core import MasterEntity, UuidEntity


@dataclass(eq=False, kw_only=True)
class RefreshTokenRecord(UuidEntity, MasterEntity):
    # Inherited `id` is the jti — the public half of the token.
    user_id: UUID
    tenant_id: UUID
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None = None
    replaced_by: UUID | None = None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at
