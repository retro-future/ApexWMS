"""User-management schemas (Owner endpoints)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from application.dtos import InviteResult, UserWithRole
from domain.roles import Role


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: Role
    is_active: bool

    @classmethod
    def from_entry(cls, entry: UserWithRole) -> UserResponse:
        return cls(
            id=entry.user.id,
            email=entry.user.email,
            full_name=entry.user.full_name,
            role=entry.role,
            is_active=entry.user.is_active,
        )


class InviteRequest(BaseModel):
    email: EmailStr
    role: Role


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
    role: Role
