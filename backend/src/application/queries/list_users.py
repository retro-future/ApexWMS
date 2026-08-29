"""List the people who work at this store, with their roles.

Reads the tenant's own ``employees`` table, never MasterDB — which is why
one store's staff list cannot surface another's.
"""

from application.common.repository import TenantDbRepository
from application.common.specification import Specification
from application.core import IRequestHandler, Query, ResultWithData
from application.models import EmployeeListItem
from domain.entities import Employee
from infrastructure.persistence.tenant.models import EmployeeModel


class ListUsersQuery(Query[ResultWithData[list[EmployeeListItem]]]):
    pass


class ListUsersHandler(
    IRequestHandler[ResultWithData[list[EmployeeListItem]], ListUsersQuery]
):
    def __init__(self, employees: TenantDbRepository[Employee, EmployeeModel]) -> None:
        self._employees = employees

    async def handle(
        self, request: ListUsersQuery
    ) -> ResultWithData[list[EmployeeListItem]]:
        roster = Specification(EmployeeModel).order(
            EmployeeModel.created_at, EmployeeModel.id
        )
        employees = await self._employees.find(roster)
        return ResultWithData[list[EmployeeListItem]].succeed_with_data(
            [EmployeeListItem.from_entity(e) for e in employees]
        )
