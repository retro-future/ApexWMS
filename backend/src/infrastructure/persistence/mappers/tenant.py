from domain.entities import Tenant
from domain.enums import TenantStatus
from infrastructure.persistence.master.models import TenantModel


class TenantMapper:
    model: type[TenantModel] = TenantModel

    def to_entity(self, model: TenantModel) -> Tenant:
        return Tenant(
            id=model.id,
            name=model.name,
            slug=model.slug,
            status=TenantStatus(model.status),
            created_at=model.created_at,
        )

    def to_model(self, entity: Tenant, model: TenantModel | None = None) -> TenantModel:
        model = model or TenantModel(id=entity.id)
        model.name = entity.name
        model.slug = entity.slug
        model.status = entity.status.value
        model.created_at = entity.created_at
        return model
