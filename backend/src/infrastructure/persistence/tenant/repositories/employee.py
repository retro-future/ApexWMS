from uuid import UUID

from sqlalchemy import func, select

from domain.entities import Employee
from domain.roles import TenantRole
from infrastructure.persistence.tenant.models import EmployeeModel

from .base import TenantCrudRepository


class SqlEmployeeRepository(TenantCrudRepository[Employee, UUID, EmployeeModel]):
    """Keyed by the master ``User.id`` — see ``domain.entities.employee``."""

    model = EmployeeModel

    def _key(self, employee: Employee) -> UUID:
        return employee.id

    def _to_entity(self, row: EmployeeModel) -> Employee:
        return Employee(
            id=row.id,
            email=row.email,
            full_name=row.full_name,
            role=TenantRole(row.role),
            is_active=row.is_active,
            created_at=row.created_at,
        )

    def _to_model(self, employee: Employee) -> EmployeeModel:
        return EmployeeModel(
            id=employee.id,
            email=employee.email,
            full_name=employee.full_name,
            role=employee.role.value,
            is_active=employee.is_active,
            created_at=employee.created_at,
        )

    def _apply(self, row: EmployeeModel, employee: Employee) -> None:
        row.email = employee.email
        row.full_name = employee.full_name
        row.role = employee.role.value
        row.is_active = employee.is_active

    async def get_by_email(self, email: str) -> Employee | None:
        row = await self._session.scalar(
            select(EmployeeModel).where(EmployeeModel.email == email)
        )
        return self._to_entity(row) if row else None

    async def list_all(self) -> list[Employee]:
        rows = await self._session.scalars(
            select(EmployeeModel).order_by(EmployeeModel.created_at)
        )
        return [self._to_entity(r) for r in rows]

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
