"""Tenant settings: read for any member, write for the Owner (PRD §2.1)."""

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Response

from application.commands.set_tenant_logo import (
    SetTenantLogoCommand,
    SetTenantLogoHandler,
)
from application.commands.update_tenant_settings import (
    UpdateTenantSettingsCommand,
    UpdateTenantSettingsHandler,
)
from application.core import ResultWithData
from application.dtos import CurrentUser
from application.models import TenantSettingsData
from application.queries.get_tenant_logo import (
    GetTenantLogoHandler,
    GetTenantLogoQuery,
)
from application.queries.get_tenant_settings import (
    GetTenantSettingsHandler,
    GetTenantSettingsQuery,
)
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.get("/tenant")
async def get_settings(
    current: FromDishka[CurrentUser], handler: FromDishka[GetTenantSettingsHandler]
) -> ResultWithData[TenantSettingsData]:
    require(current, Permission.TENANT_SETTINGS_VIEW)
    return await handler.handle(GetTenantSettingsQuery())


@router.put("/tenant")
async def update_settings(
    body: UpdateTenantSettingsCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UpdateTenantSettingsHandler],
) -> ResultWithData[TenantSettingsData]:
    require(current, Permission.TENANT_SETTINGS_MANAGE)
    return await handler.handle(body)


@router.get("/tenant/logo", response_class=Response)
async def get_logo(
    current: FromDishka[CurrentUser], handler: FromDishka[GetTenantLogoHandler]
) -> Response:
    """The letterhead image itself — 404 while the store has not set one."""
    require(current, Permission.TENANT_SETTINGS_VIEW)
    result = await handler.handle(GetTenantLogoQuery())
    assert result.data is not None
    logo = result.data
    return Response(content=logo.content, media_type=logo.content_type)


@router.put("/tenant/logo")
async def set_logo(
    body: SetTenantLogoCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[SetTenantLogoHandler],
) -> ResultWithData[TenantSettingsData]:
    """FR-8.1: a base64 PNG or JPEG, or a null body to clear it."""
    require(current, Permission.TENANT_SETTINGS_MANAGE)
    return await handler.handle(body)
