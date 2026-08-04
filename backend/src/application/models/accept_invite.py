"""Response payload for accepting an invitation."""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from domain.entities import Invitation, User


class AcceptInviteData(CamelModel):
    user_id: UUID
    tenant_id: UUID | None

    @classmethod
    def from_entity(cls, user: User, invitation: Invitation) -> AcceptInviteData:
        return cls(user_id=user.id, tenant_id=invitation.tenant_id)
