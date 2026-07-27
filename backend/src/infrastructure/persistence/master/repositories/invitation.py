from uuid import UUID

from domain.entities import Invitation, InvitationKind
from domain.roles import AppRole, TenantRole
from infrastructure.persistence.master.models import InvitationModel

from .base import MasterCrudRepository


class SqlInvitationRepository(MasterCrudRepository[Invitation, UUID, InvitationModel]):
    model = InvitationModel

    def _key(self, entity: Invitation) -> UUID:
        return entity.id

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

    def _to_model(self, entity: Invitation) -> InvitationModel:
        return InvitationModel(
            id=entity.id,
            email=entity.email,
            kind=entity.kind.value,
            tenant_id=entity.tenant_id,
            tenant_role=entity.tenant_role.value if entity.tenant_role else None,
            app_role=entity.app_role.value if entity.app_role else None,
            token_hash=entity.token_hash,
            expires_at=entity.expires_at,
            accepted_at=entity.accepted_at,
            created_by=entity.created_by,
        )

    def _apply(self, row: InvitationModel, entity: Invitation) -> None:
        row.accepted_at = entity.accepted_at
