"""Change someone's role at this store, guarded against locking it out.

Operates on the ``Employee`` row: a role is a fact about a person *at one
store*, so changing it never touches their master login identity.
"""

from uuid import UUID

from application.errors import LastOwnerError, NotFoundError
from application.ports import EmployeeRepository, TenantUnitOfWork
from domain.roles import TenantRole


class ChangeUserRole:
    def __init__(self, employees: EmployeeRepository, uow: TenantUnitOfWork) -> None:
        self._employees = employees
        self._uow = uow

    async def execute(self, target_user_id: UUID, new_role: TenantRole) -> None:
        employee = await self._employees.get(target_user_id)
        if employee is None:
            raise NotFoundError("no such employee at this store")
        if (
            employee.role is TenantRole.OWNER
            and new_role is not TenantRole.OWNER
            and await self._employees.count_owners() <= 1
        ):
            raise LastOwnerError("a store must keep at least one Owner")
        employee.role = new_role
        await self._employees.update(employee)
        await self._uow.commit()
