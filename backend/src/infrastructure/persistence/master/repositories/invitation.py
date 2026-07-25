from uuid import UUID

from domain.entities import Invitation, InvitationKind
from domain.roles import AppRole, TenantRole
from infrastructure.persistence.master.models import InvitationModel

from .base import MasterCrudRepository


class SqlInvitationRepository(MasterCrudRepository[Invitation, UUID, InvitationModel]):
    model = InvitationModel

    def _key(self, invitation: Invitation) -> UUID:
        return invitation.id

    def _to_entity(self, row: InvitationModel) -> Invitation:
        return Invitation(
            id=row.id,
            email=row.email,
            kind=InvitationKind(row.kind),
            tenant_id=row.tenant_id,
            tenant_role=TenantRole(row.tenant_role) if row.tenant_role else None,
            app_role=AppRole(row.app_role) if row.app_role else None,
            token_hash=row.token_hash,
            expires_at=row.expires_at,
            created_by=row.created_by,
            accepted_at=row.accepted_at,
        )

    def _to_model(self, invitation: Invitation) -> InvitationModel:
        return InvitationModel(
            id=invitation.id,
            email=invitation.email,
            kind=invitation.kind.value,
            tenant_id=invitation.tenant_id,
            tenant_role=invitation.tenant_role.value if invitation.tenant_role else None,
            app_role=invitation.app_role.value if invitation.app_role else None,
            token_hash=invitation.token_hash,
            expires_at=invitation.expires_at,
            accepted_at=invitation.accepted_at,
            created_by=invitation.created_by,
        )

    def _apply(self, row: InvitationModel, invitation: Invitation) -> None:
        row.accepted_at = invitation.accepted_at
