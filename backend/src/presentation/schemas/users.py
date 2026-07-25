"""Staff-management schemas.

These describe ``Employee`` rows — a person's presence at *this* store —
not the master login identity behind them.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from application.dtos import InviteResult
from domain.entities import Employee
from domain.roles import TenantRole


class UserResponse(BaseModel):
    # The master user id: Employee.id is that same value by contract.
    id: UUID
    email: str
    full_name: str
    role: TenantRole
    is_active: bool

    @classmethod
    def from_employee(cls, employee: Employee) -> UserResponse:
        return cls(
            id=employee.id,
            email=employee.email,
            full_name=employee.full_name,
            role=employee.role,
            is_active=employee.is_active,
        )


class InviteRequest(BaseModel):
    email: EmailStr
    role: TenantRole


class InviteResponse(BaseModel):
    invitation_id: UUID
    # Handed to the invitee by the Owner (no email in M1); consumed by
    # POST /auth/accept-invite.
    token: str
    expires_at: datetime

    @classmethod
    def from_result(cls, result: InviteResult) -> InviteResponse:
        return cls(
            invitation_id=result.invitation_id,
            token=result.token,
            expires_at=result.expires_at,
        )


class RoleUpdateRequest(BaseModel):
    role: TenantRole
