"""List the people who work at this store, with their roles.

Reads the tenant's own ``employees`` table, never MasterDB — which is why
one store's staff list cannot surface another's.
"""

from application.core import IRequestHandler, Query, ResultWithData
from application.models import EmployeeListItem
from application.ports import EmployeeRepository


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
            [EmployeeListItem.from_entity(e) for e in employees]
        )
