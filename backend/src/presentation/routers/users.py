"""User management — Owner only (PRD §2.1: manage users & roles)."""

from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter

from application.dtos import CurrentUser
from application.use_cases import ChangeUserRole, InviteUser, ListUsers
from domain.roles import Role
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
    require(current, Role.OWNER)
    entries = await use_case.execute(current.tenant_id)
    return [UserResponse.from_entry(e) for e in entries]


@router.post("/invite", response_model=InviteResponse, status_code=201)
async def invite(
    body: InviteRequest,
    current: FromDishka[CurrentUser],
    use_case: FromDishka[InviteUser],
) -> InviteResponse:
    require(current, Role.OWNER)
    result = await use_case.execute(
        current.tenant_id, body.email, body.role, created_by=current.user_id
    )
    return InviteResponse.from_result(result)


@router.patch("/{user_id}/role", status_code=204)
async def change_role(
    user_id: UUID,
    body: RoleUpdateRequest,
    current: FromDishka[CurrentUser],
    use_case: FromDishka[ChangeUserRole],
) -> None:
    require(current, Role.OWNER)
    await use_case.execute(current.tenant_id, user_id, body.role)
