from domain.entities import UserAppRole
from domain.enums import AppRole
from infrastructure.persistence.master.models import UserAppRoleModel


class UserAppRoleMapper:
    model: type[UserAppRoleModel] = UserAppRoleModel

    def to_entity(self, model: UserAppRoleModel) -> UserAppRole:
        return UserAppRole(id=model.id, user_id=model.user_id, role=AppRole(model.role))

    def to_model(
        self, entity: UserAppRole, model: UserAppRoleModel | None = None
    ) -> UserAppRoleModel:
        model = model or UserAppRoleModel(id=entity.id)
        model.user_id = entity.user_id
        model.role = entity.role.value
        return model
