"""Auth endpoints: login, refresh, invite acceptance, password change, /me.

There is no sign-up route. A store exists because a SuperAdmin created it
with ``apexwms create-tenant`` (PRD §3.4).

None of these routes requires a tenant header. Identity is master-side, so
login authenticates before any store is named, and the tenant claim is
stamped server-side from the user's own record. ``X-Tenant`` is optional
here and only matters for someone who works at more than one store.
"""

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter

from application.dtos import AcceptInviteCommand, CurrentUser, RequestedTenant
from application.use_cases import (
    AcceptInvite,
    ChangePassword,
    GetMe,
    Login,
    RefreshTokens,
)
from presentation.schemas.auth import (
    AcceptInviteRequest,
    AcceptInviteResponse,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    RefreshRequest,
    TokenPairResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"], route_class=DishkaRoute)


@router.post("/login", response_model=LoginResponse, response_model_exclude_none=True)
async def login(
    body: LoginRequest,
    use_case: FromDishka[Login],
    tenant: FromDishka[RequestedTenant],
) -> LoginResponse:
    result = await use_case.execute(body.email, body.password, tenant.tenant_id)
    return LoginResponse.from_result(result)


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(
    body: RefreshRequest,
    use_case: FromDishka[RefreshTokens],
    tenant: FromDishka[RequestedTenant],
) -> TokenPairResponse:
    tokens = await use_case.execute(body.refresh_token, tenant.tenant_id)
    return TokenPairResponse(
        access_token=tokens.access_token, refresh_token=tokens.refresh_token
    )


@router.post("/accept-invite", response_model=AcceptInviteResponse, status_code=201)
async def accept_invite(
    body: AcceptInviteRequest, use_case: FromDishka[AcceptInvite]
) -> AcceptInviteResponse:
    result = await use_case.execute(
        AcceptInviteCommand(token=body.token, password=body.password, full_name=body.full_name)
    )
    return AcceptInviteResponse(user_id=result.user_id, tenant_id=result.tenant_id)


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    current: FromDishka[CurrentUser],
    use_case: FromDishka[ChangePassword],
) -> None:
    await use_case.execute(current.user_id, body.current_password, body.new_password)


@router.get("/me", response_model=MeResponse, response_model_exclude_none=True)
async def me(
    current: FromDishka[CurrentUser],
    use_case: FromDishka[GetMe],
) -> MeResponse:
    return MeResponse.from_view(await use_case.execute(current))
