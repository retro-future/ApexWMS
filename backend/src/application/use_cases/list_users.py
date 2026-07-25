"""List the people who work at this store, with their roles.

Reads the tenant's own ``employees`` table, never MasterDB — which is why
one store's staff list cannot surface another's.
"""

from application.ports import EmployeeRepository
from domain.entities import Employee


class ListUsers:
    def __init__(self, employees: EmployeeRepository) -> None:
        self._employees = employees

    async def execute(self) -> list[Employee]:
        return await self._employees.list_all()
