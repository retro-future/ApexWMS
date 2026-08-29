from domain.entities import Employee
from domain.enums import TenantRole
from infrastructure.persistence.tenant.models import EmployeeModel


class EmployeeMapper:
    model: type[EmployeeModel] = EmployeeModel

    def to_entity(self, model: EmployeeModel) -> Employee:
        return Employee(
            id=model.id,
            email=model.email,
            full_name=model.full_name,
            role=TenantRole(model.role),
            is_active=model.is_active,
            created_at=model.created_at,
        )

    def to_model(self, entity: Employee, model: EmployeeModel | None = None) -> EmployeeModel:
        model = model or EmployeeModel(id=entity.id)
        model.email = entity.email
        model.full_name = entity.full_name
        model.role = entity.role.value
        model.is_active = entity.is_active
        model.created_at = entity.created_at
        return model
