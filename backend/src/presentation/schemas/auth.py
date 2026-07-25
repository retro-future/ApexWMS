"""Auth request/response schemas — structural validation only (PRD §7.3)."""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from application.dtos import LoginResult, MeView
from domain.roles import AppRole, TenantRole


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """No tenant field: email is unique platform-wide, and which store the
    token speaks for is decided server-side (PRD §3.3). An ``X-Tenant``
    header may still name one, for a person who works at several."""

    email: EmailStr
    password: str


class LoginResponse(TokenPairResponse):
    # None for a platform operator, whose token carries no tenant claim.
    tenant_id: UUID | None = None
    role: TenantRole | None = None
    app_roles: list[AppRole] = Field(default_factory=list)
    # True for someone still on a provisioned temporary password.
    must_change_password: bool

    @classmethod
    def from_result(cls, result: LoginResult) -> LoginResponse:
        return cls(
            access_token=result.tokens.access_token,
            refresh_token=result.tokens.refresh_token,
            tenant_id=result.tenant_id,
            role=result.tenant_role,
            app_roles=list(result.app_roles),
            must_change_password=result.must_change_password,
        )


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=200)


class AcceptInviteRequest(BaseModel):
    token: str
    password: str | None = Field(default=None, min_length=8, max_length=200)
    full_name: str | None = Field(default=None, min_length=1, max_length=200)


class AcceptInviteResponse(BaseModel):
    user_id: UUID
    tenant_id: UUID | None = None


class MeResponse(BaseModel):
    user_id: UUID
    email: str
    full_name: str
    must_change_password: bool
    tenant_id: UUID | None = None
    role: TenantRole | None = None
    app_roles: list[AppRole] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)

    @classmethod
    def from_view(cls, view: MeView) -> MeResponse:
        return cls(
            user_id=view.user_id,
            email=view.email,
            full_name=view.full_name,
            must_change_password=view.must_change_password,
            tenant_id=view.tenant_id,
            role=view.tenant_role,
            app_roles=list(view.app_roles),
            permissions=sorted(view.permissions),
        )
