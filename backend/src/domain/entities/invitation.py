"""An invitation to join the platform or a store (FR-1.5): single-use, expiring.

Lives in MasterDB, not in the tenant it points at — accepting one creates
a *login identity*, and the invitee has no tenant context until they do.
Storing it centrally is what lets acceptance work without the caller
naming a tenant first.

Two shapes share the row, distinguished by ``kind``:

* ``EMPLOYEE`` — ``tenant_id`` and ``tenant_role`` set. Acceptance creates
  a User *and* an Employee in that store's database.
* ``APP_USER`` — both null, ``app_role`` set. Acceptance creates a
  platform operator; no tenant database is touched at all.

Only a hash of the invite secret is stored; the full token exists once, in
the response returned to whoever sent the invitation.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from domain.core import MasterEntity, UuidEntity
from domain.roles import AppRole, TenantRole


class InvitationKind(StrEnum):
    EMPLOYEE = "employee"
    APP_USER = "app_user"


@dataclass(eq=False, kw_only=True)
class Invitation(UuidEntity, MasterEntity):
    email: str
    kind: InvitationKind
    token_hash: str
    expires_at: datetime
    created_by: UUID
    tenant_id: UUID | None = None
    tenant_role: TenantRole | None = None
    app_role: AppRole | None = None
    accepted_at: datetime | None = None

    @property
    def is_accepted(self) -> bool:
        return self.accepted_at is not None

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at
