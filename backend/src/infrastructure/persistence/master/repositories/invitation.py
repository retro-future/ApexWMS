from uuid import UUID

from domain.entities import Invitation
from domain.roles import Role
from infrastructure.persistence.master.models import InvitationModel

from .base import MasterCrudRepository


class SqlInvitationRepository(MasterCrudRepository[Invitation, UUID, InvitationModel]):
    model = InvitationModel

    def _key(self, invitation: Invitation) -> UUID:
        return invitation.id

    def _to_entity(self, row: InvitationModel) -> Invitation:
        return Invitation(
            id=row.id,
            tenant_id=row.tenant_id,
            email=row.email,
            role=Role(row.role),
            token_hash=row.token_hash,
            expires_at=row.expires_at,
            created_by=row.created_by,
            accepted_at=row.accepted_at,
        )

    def _to_model(self, invitation: Invitation) -> InvitationModel:
        return InvitationModel(
            id=invitation.id,
            tenant_id=invitation.tenant_id,
            email=invitation.email,
            role=invitation.role.value,
            token_hash=invitation.token_hash,
            expires_at=invitation.expires_at,
            accepted_at=invitation.accepted_at,
            created_by=invitation.created_by,
        )

    def _apply(self, row: InvitationModel, invitation: Invitation) -> None:
        row.accepted_at = invitation.accepted_at
