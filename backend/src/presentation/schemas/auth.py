"""Auth request/response schemas — structural validation only (PRD §7.3)."""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from application.dtos import LoginResult, MeView, SignUpResult
from domain.roles import Role

DEFAULT_TIMEZONE = "Asia/Tashkent"


class SignUpRequest(BaseModel):
    tenant_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    full_name: str = Field(min_length=1, max_length=200)
    timezone: str = DEFAULT_TIMEZONE


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class SignUpResponse(TokenPairResponse):
    tenant_id: UUID

    @classmethod
    def from_result(cls, result: SignUpResult) -> SignUpResponse:
        return cls(
            tenant_id=result.tenant_id,
            access_token=result.tokens.access_token,
            refresh_token=result.tokens.refresh_token,
        )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    # Required only when the user belongs to several tenants (FR-1.3).
    tenant_id: UUID | None = None


class TenantChoiceResponse(BaseModel):
    tenant_id: UUID
    name: str


class LoginResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    tenant_id: UUID | None = None
    role: Role | None = None
    # Present instead of tokens when a tenant must be chosen first.
    tenants: list[TenantChoiceResponse] | None = None

    @classmethod
    def from_result(cls, result: LoginResult) -> LoginResponse:
        if result.tokens is None:
            return cls(
                tenants=[
                    TenantChoiceResponse(tenant_id=c.tenant_id, name=c.name)
                    for c in result.tenant_choices or []
                ]
            )
        return cls(
            access_token=result.tokens.access_token,
            refresh_token=result.tokens.refresh_token,
            token_type="bearer",
            tenant_id=result.tenant_id,
            role=result.role,
        )


class RefreshRequest(BaseModel):
    refresh_token: str


class AcceptInviteRequest(BaseModel):
    token: str
    password: str | None = Field(default=None, min_length=8, max_length=200)
    full_name: str | None = Field(default=None, min_length=1, max_length=200)


class AcceptInviteResponse(BaseModel):
    tenant_id: UUID


class MeResponse(BaseModel):
    user_id: UUID
    email: str
    full_name: str
    tenant_id: UUID
    role: Role

    @classmethod
    def from_view(cls, view: MeView) -> MeResponse:
        return cls(
            user_id=view.user_id,
            email=view.email,
            full_name=view.full_name,
            tenant_id=view.tenant_id,
            role=view.role,
        )
