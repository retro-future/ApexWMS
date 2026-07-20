"""An invitation to join a tenant (FR-1.5): single-use, expiring.

Only a hash of the invite secret is stored; the full token exists once,
in the response returned to the inviting Owner.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.core import MasterEntity, UuidEntity
from domain.roles import Role


@dataclass(eq=False, kw_only=True)
class Invitation(UuidEntity, MasterEntity):
    tenant_id: UUID
    email: str
    role: Role
    token_hash: str
    expires_at: datetime
    created_by: UUID
    accepted_at: datetime | None = None

    @property
    def is_accepted(self) -> bool:
        return self.accepted_at is not None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at
