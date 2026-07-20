"""Tenant settings: read for any member, write for the Owner (PRD §2.1)."""


from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter

from application.dtos import CurrentUser
from application.use_cases import GetTenantSettings, UpdateTenantSettings
from domain.roles import Role
from presentation.schemas.settings import (
    TenantSettingsResponse,
    TenantSettingsUpdateRequest,
)
from presentation.security import require

router = APIRouter(prefix="/settings", tags=["settings"], route_class=DishkaRoute)


@router.get("/tenant", response_model=TenantSettingsResponse)
async def get_settings(
    current: FromDishka[CurrentUser],
    use_case: FromDishka[GetTenantSettings],
) -> TenantSettingsResponse:
    return TenantSettingsResponse(timezone=await use_case.execute())


@router.put("/tenant", response_model=TenantSettingsResponse)
async def update_settings(
    body: TenantSettingsUpdateRequest,
    current: FromDishka[CurrentUser],
    use_case: FromDishka[UpdateTenantSettings],
) -> TenantSettingsResponse:
    require(current, Role.OWNER)
    return TenantSettingsResponse(timezone=await use_case.execute(body.timezone))
