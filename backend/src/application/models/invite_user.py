"""Response payload for a newly created invitation.

M1 decision: the invite token is returned in the response for the Owner
to deliver; no email is sent.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from domain.entities import Invitation


class InviteResultData(CamelModel):
    invitation_id: UUID
    token: str
    expires_at: datetime

    @classmethod
    def from_entity(cls, invitation: Invitation, secret: str) -> InviteResultData:
        return cls(
            invitation_id=invitation.id,
            token=f"{invitation.id}.{secret}",
            expires_at=invitation.expires_at,
        )
