"""Staff management at one store (PRD §2.1: manage users & roles)."""

from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends

from application.commands.change_user_role import ChangeUserRoleCommand, ChangeUserRoleHandler
from application.commands.invite_user import (
    InviteEmployeeCommand,
    InviteResultData,
    InviteUserHandler,
)
from application.core import ResultWithData
from application.dtos import CurrentUser
from application.queries.list_users import EmployeeListItem, ListUsersHandler, ListUsersQuery
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/users",
    tags=["users"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.get("")
async def list_users(
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListUsersHandler],
) -> ResultWithData[list[EmployeeListItem]]:
    require(current, Permission.Users.View)
    return await handler.handle(ListUsersQuery())


@router.post("/invite", status_code=201)
async def invite(
    body: InviteEmployeeCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[InviteUserHandler],
) -> ResultWithData[InviteResultData]:
    require(current, Permission.Users.Manage)
    # No tenant check here: InviteUserHandler is built from the resolved
    # tenant, so a request that named no store never reaches this route.
    return await handler.handle(body)


@router.patch("/{user_id}/role", status_code=204)
async def change_role(
    user_id: UUID,
    body: ChangeUserRoleCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ChangeUserRoleHandler],
) -> None:
    require(current, Permission.Users.Manage)
    await handler.handle(body.model_copy(update={"target_user_id": user_id}))
