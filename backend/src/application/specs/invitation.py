"""Reads for pending invitations (MasterDB, ADR 0007)."""

from uuid import UUID

from application.common.specification import Specification
from infrastructure.persistence.master.models import InvitationModel


class InvitationForWrite(Specification[InvitationModel]):
    def __init__(self, invitation_id: UUID) -> None:
        super().__init__(InvitationModel)
        self.invitation_id = invitation_id
        self.where(InvitationModel.id == invitation_id)
        self.lock()
