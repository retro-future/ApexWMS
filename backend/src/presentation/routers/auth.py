"""Auth endpoints: login, refresh, invite acceptance, password change, /me.

There is no sign-up route. A store exists because a SuperAdmin created it
with ``apexwms create-tenant`` (PRD §3.4).

None of these routes requires a tenant header. Identity is master-side, so
login authenticates before any store is named, and the tenant claim is
stamped server-side from the user's own record. ``X-Tenant`` is optional
here and only matters for someone who works at more than one store.
"""

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends

from application.commands.accept_invite import AcceptInviteCommand, AcceptInviteHandler
from application.commands.change_password import (
    ChangePasswordCommand,
    ChangePasswordHandler,
)
from application.commands.login import LoginCommand, LoginHandler
from application.commands.refresh_tokens import RefreshTokensCommand, RefreshTokensHandler
from application.core import ResultWithData
from application.models import AcceptInviteData, AuthTokensData, LoginData, MeData
from application.queries.get_me import GetMeHandler, GetMeQuery
from presentation.security import bearer_scheme

router = APIRouter(prefix="/auth", tags=["auth"], route_class=DishkaRoute)


@router.post("/login", response_model_exclude_none=True)
async def login(
    body: LoginCommand, handler: FromDishka[LoginHandler]
) -> ResultWithData[LoginData]:
    return await handler.handle(body)


@router.post("/refresh")
async def refresh(
    body: RefreshTokensCommand, handler: FromDishka[RefreshTokensHandler]
) -> ResultWithData[AuthTokensData]:
    return await handler.handle(body)


@router.post("/accept-invite", status_code=201)
async def accept_invite(
    body: AcceptInviteCommand, handler: FromDishka[AcceptInviteHandler]
) -> ResultWithData[AcceptInviteData]:
    return await handler.handle(body)


@router.post("/change-password", status_code=204, dependencies=[Depends(bearer_scheme)])
async def change_password(
    body: ChangePasswordCommand, handler: FromDishka[ChangePasswordHandler]
) -> None:
    await handler.handle(body)


@router.get("/me", response_model_exclude_none=True, dependencies=[Depends(bearer_scheme)])
async def me(handler: FromDishka[GetMeHandler]) -> ResultWithData[MeData]:
    return await handler.handle(GetMeQuery())
