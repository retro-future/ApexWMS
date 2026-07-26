"""Tenant settings: read for any member, write for the Owner (PRD §2.1)."""

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter

from application.commands.update_tenant_settings import (
    UpdateTenantSettingsCommand,
    UpdateTenantSettingsHandler,
)
from application.core import ResultWithData
from application.dtos import CurrentUser
from application.queries.get_tenant_settings import (
    GetTenantSettingsHandler,
    GetTenantSettingsQuery,
    TenantSettingsData,
)
from domain.permissions import Permission
from presentation.security import require

router = APIRouter(prefix="/settings", tags=["settings"], route_class=DishkaRoute)


@router.get("/tenant")
async def get_settings(
    current: FromDishka[CurrentUser], handler: FromDishka[GetTenantSettingsHandler]
) -> ResultWithData[TenantSettingsData]:
    require(current, Permission.TenantSettings.View)
    return await handler.handle(GetTenantSettingsQuery())


@router.put("/tenant")
async def update_settings(
    body: UpdateTenantSettingsCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UpdateTenantSettingsHandler],
) -> ResultWithData[TenantSettingsData]:
    require(current, Permission.TenantSettings.Manage)
    return await handler.handle(body)
