from uuid import UUID

from sqlalchemy import func, select

from domain.entities import Employee
from domain.roles import TenantRole
from infrastructure.persistence.tenant.models import EmployeeModel

from .base import TenantCrudRepository


class SqlEmployeeRepository(TenantCrudRepository[Employee, UUID, EmployeeModel]):
    """Keyed by the master ``User.id`` — see ``domain.entities.employee``."""

    model = EmployeeModel


    def _to_entity(self, row: EmployeeModel) -> Employee:
        return Employee(
            id=row.id,
            email=row.email,
            full_name=row.full_name,
            role=TenantRole(row.role),
            is_active=row.is_active,
            created_at=row.created_at,
        )

    def _to_model(self, entity: Employee) -> EmployeeModel:
        return EmployeeModel(
            id=entity.id,
            email=entity.email,
            full_name=entity.full_name,
            role=entity.role.value,
            is_active=entity.is_active,
            created_at=entity.created_at,
        )

    def _apply(self, row: EmployeeModel, entity: Employee) -> None:
        row.email = entity.email
        row.full_name = entity.full_name
        row.role = entity.role.value
        row.is_active = entity.is_active

    async def get_by_email(self, email: str) -> Employee | None:
        return await self._find_one(EmployeeModel.email == email)

    async def list_all(self) -> list[Employee]:
        return await self._find_many(select(EmployeeModel).order_by(EmployeeModel.created_at))

    async def count_owners(self) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(EmployeeModel)
            .where(
                EmployeeModel.role == TenantRole.OWNER.value,
                EmployeeModel.is_active.is_(True),
            )
        )
        return count or 0
