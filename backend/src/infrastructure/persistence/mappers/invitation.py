from domain.entities import Invitation, InvitationKind
from domain.enums import AppRole, TenantRole
from infrastructure.persistence.master.models import InvitationModel


class InvitationMapper:
    model: type[InvitationModel] = InvitationModel

    def to_entity(self, model: InvitationModel) -> Invitation:
        return Invitation(
            id=model.id,
            email=model.email,
            kind=InvitationKind(model.kind),
            tenant_id=model.tenant_id,
            tenant_role=TenantRole(model.tenant_role) if model.tenant_role else None,
            app_role=AppRole(model.app_role) if model.app_role else None,
            token_hash=model.token_hash,
            expires_at=model.expires_at,
            created_by=model.created_by,
            accepted_at=model.accepted_at,
        )

    def to_model(
        self, entity: Invitation, model: InvitationModel | None = None
    ) -> InvitationModel:
        model = model or InvitationModel(id=entity.id)
        model.email = entity.email
        model.kind = entity.kind.value
        model.tenant_id = entity.tenant_id
        model.tenant_role = entity.tenant_role.value if entity.tenant_role else None
        model.app_role = entity.app_role.value if entity.app_role else None
        model.token_hash = entity.token_hash
        model.expires_at = entity.expires_at
        model.accepted_at = entity.accepted_at
        model.created_by = entity.created_by
        return model
