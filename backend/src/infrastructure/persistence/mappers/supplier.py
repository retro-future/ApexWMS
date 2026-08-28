from domain.entities import Supplier
from infrastructure.persistence.tenant.models import SupplierModel


class SupplierMapper:
    model: type[SupplierModel] = SupplierModel

    def to_entity(self, model: SupplierModel) -> Supplier:
        return Supplier(
            id=model.id,
            name=model.name,
            contact_name=model.contact_name,
            phone=model.phone,
            email=model.email,
            is_active=model.is_active,
            created_at=model.created_at,
        )

    def to_model(self, entity: Supplier, model: SupplierModel | None = None) -> SupplierModel:
        model = model or SupplierModel(id=entity.id)
        model.name = entity.name
        model.contact_name = entity.contact_name
        model.phone = entity.phone
        model.email = entity.email
        model.is_active = entity.is_active
        model.created_at = entity.created_at
        return model
