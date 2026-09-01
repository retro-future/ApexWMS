"""Change someone's role at this store, guarded against locking it out.

Operates on the ``Employee`` row: a role is a fact about a person *at one
store*, so changing it never touches their master login identity.

``target_user_id`` is a URL path segment, not something a DI-resolvable
type can supply — it is not part of the client-facing body schema at all
(``ChangeUserRoleCommandPayload``), and is filled in by the router once the
path is parsed (see ``presentation/routers/users.py``).
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, Result
from application.errors import LastOwnerError, NotFoundError
from application.ports import TenantUnitOfWork
from application.specs import ActiveOwners, EmployeeForWrite
from domain.entities import Employee
from domain.enums import TenantRole
from infrastructure.persistence.tenant.models import EmployeeModel


class ChangeUserRoleCommandPayload(CamelModel):
    role: TenantRole


class ChangeUserRoleCommand(ChangeUserRoleCommandPayload, Command[Result]):
    target_user_id: UUID


class ChangeUserRoleHandler(IRequestHandler[Result, ChangeUserRoleCommand]):
    def __init__(
        self,
        employees: TenantDbRepository[Employee, EmployeeModel],
        uow: TenantUnitOfWork,
    ) -> None:
        self._employees = employees
        self._uow = uow

    async def handle(self, request: ChangeUserRoleCommand) -> Result:
        employee = await self._employees.find_one(EmployeeForWrite(request.target_user_id))
        if employee is None:
            raise NotFoundError(
                "no such employee at this store",
                key="not_found",
                subject_key="employee",
            )
        if (
            employee.role is TenantRole.OWNER
            and request.role is not TenantRole.OWNER
            and await self._employees.count(ActiveOwners()) <= 1
        ):
            raise LastOwnerError("a store must keep at least one Owner")
        employee.role = request.role
        await self._employees.update(employee)
        await self._uow.commit()
        return Result.succeed()
