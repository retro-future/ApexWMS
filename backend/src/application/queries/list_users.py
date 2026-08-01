"""List the people who work at this store, with their roles.

Reads the tenant's own ``employees`` table, never MasterDB — which is why
one store's staff list cannot surface another's.
"""

from uuid import UUID

from application.core import CamelModel, IRequestHandler, Query, ResultWithData
from application.ports import EmployeeRepository
from domain.entities import Employee
from domain.enums import TenantRole


class EmployeeListItem(CamelModel):
    # The master user id: Employee.id is that same value by contract.
    id: UUID
    email: str
    full_name: str
    role: TenantRole
    is_active: bool

    @classmethod
    def from_employee(cls, employee: Employee) -> EmployeeListItem:
        return cls(
            id=employee.id,
            email=employee.email,
            full_name=employee.full_name,
            role=employee.role,
            is_active=employee.is_active,
        )


class ListUsersQuery(Query[ResultWithData[list[EmployeeListItem]]]):
    pass


class ListUsersHandler(
    IRequestHandler[ResultWithData[list[EmployeeListItem]], ListUsersQuery]
):
    def __init__(self, employees: EmployeeRepository) -> None:
        self._employees = employees

    async def handle(
        self, request: ListUsersQuery
    ) -> ResultWithData[list[EmployeeListItem]]:
        employees = await self._employees.list_all()
        return ResultWithData[list[EmployeeListItem]].succeed_with_data(
            [EmployeeListItem.from_employee(e) for e in employees]
        )
