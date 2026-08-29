"""The reads the staff use cases need, one class each.

Written against ``EmployeeModel``, not ``Employee`` (ADR 0007). The
``Employee`` row is keyed by the master ``User.id``, so a load by id
(``repo.get(user_id)``) and ``EmployeeForWrite`` both take a user id. The
roster read and the invite uniqueness probe are inline in the handlers.
"""

from uuid import UUID

from application.common.specification import Specification
from domain.enums import TenantRole
from infrastructure.persistence.tenant.models import EmployeeModel


class EmployeeForWrite(Specification[EmployeeModel]):
    """Locks the row for a command that loads an employee to change a role."""

    def __init__(self, user_id: UUID) -> None:
        super().__init__(EmployeeModel)
        self.user_id = user_id
        self.where(EmployeeModel.id == user_id)
        self.lock()


class ActiveOwners(Specification[EmployeeModel]):
    """Used with ``count()`` to guard against demoting the last Owner."""

    def __init__(self) -> None:
        super().__init__(EmployeeModel)
        self.where(
            EmployeeModel.role == TenantRole.OWNER.value,
            EmployeeModel.is_active.is_(True),
        )
