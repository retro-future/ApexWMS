"""Response payload for one store employee — see ``application/queries/list_users.py``."""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
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
    def from_entity(cls, employee: Employee) -> EmployeeListItem:
        return cls(
            id=employee.id,
            email=employee.email,
            full_name=employee.full_name,
            role=employee.role,
            is_active=employee.is_active,
        )
