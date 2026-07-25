"""Staff management at one store (PRD §2.1: manage users & roles)."""

from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter

from application.dtos import CurrentUser, InviteEmployeeCommand
from application.use_cases import ChangeUserRole, InviteUser, ListUsers
from domain.permissions import Permission
from presentation.schemas.users import (
    InviteRequest,
    InviteResponse,
    RoleUpdateRequest,
    UserResponse,
)
from presentation.security import require

router = APIRouter(prefix="/users", tags=["users"], route_class=DishkaRoute)


@router.get("", response_model=list[UserResponse])
async def list_users(
    current: FromDishka[CurrentUser],
    use_case: FromDishka[ListUsers],
) -> list[UserResponse]:
    require(current, Permission.Users.View)
    return [UserResponse.from_employee(e) for e in await use_case.execute()]


@router.post("/invite", response_model=InviteResponse, status_code=201)
async def invite(
    body: InviteRequest,
    current: FromDishka[CurrentUser],
    use_case: FromDishka[InviteUser],
) -> InviteResponse:
    require(current, Permission.Users.Manage)
    # No tenant check here: InviteUser is built from the resolved tenant, so
    # a request that named no store never reaches this route.
    result = await use_case.execute(
        InviteEmployeeCommand(
            email=body.email, role=body.role, invited_by=current.user_id
        )
    )
    return InviteResponse.from_result(result)


@router.patch("/{user_id}/role", status_code=204)
async def change_role(
    user_id: UUID,
    body: RoleUpdateRequest,
    current: FromDishka[CurrentUser],
    use_case: FromDishka[ChangeUserRole],
) -> None:
    require(current, Permission.Users.Manage)
    await use_case.execute(user_id, body.role)
