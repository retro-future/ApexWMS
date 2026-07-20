"""Auth endpoints: signup, login, refresh, invite acceptance, /me."""


from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter

from application.dtos import AcceptInviteCommand, CurrentUser, SignUpCommand
from application.use_cases import AcceptInvite, GetMe, Login, RefreshTokens, SignUp
from presentation.schemas.auth import (
    AcceptInviteRequest,
    AcceptInviteResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
    RefreshRequest,
    SignUpRequest,
    SignUpResponse,
    TokenPairResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"], route_class=DishkaRoute)


@router.post("/signup", response_model=SignUpResponse, status_code=201)
async def sign_up(
    body: SignUpRequest, use_case: FromDishka[SignUp]
) -> SignUpResponse:
    result = await use_case.execute(
        SignUpCommand(
            tenant_name=body.tenant_name,
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            timezone=body.timezone,
        )
    )
    return SignUpResponse.from_result(result)


@router.post("/login", response_model=LoginResponse, response_model_exclude_none=True)
async def login(
    body: LoginRequest, use_case: FromDishka[Login]
) -> LoginResponse:
    result = await use_case.execute(body.email, body.password, body.tenant_id)
    return LoginResponse.from_result(result)


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(
    body: RefreshRequest, use_case: FromDishka[RefreshTokens]
) -> TokenPairResponse:
    tokens = await use_case.execute(body.refresh_token)
    return TokenPairResponse(
        access_token=tokens.access_token, refresh_token=tokens.refresh_token
    )


@router.post("/accept-invite", response_model=AcceptInviteResponse)
async def accept_invite(
    body: AcceptInviteRequest, use_case: FromDishka[AcceptInvite]
) -> AcceptInviteResponse:
    tenant_id = await use_case.execute(
        AcceptInviteCommand(token=body.token, password=body.password, full_name=body.full_name)
    )
    return AcceptInviteResponse(tenant_id=tenant_id)


@router.get("/me", response_model=MeResponse)
async def me(
    current: FromDishka[CurrentUser],
    use_case: FromDishka[GetMe],
) -> MeResponse:
    return MeResponse.from_view(await use_case.execute(current))
