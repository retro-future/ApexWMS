"""Handsets and their prices (PRD §8, "Stock & Unit Pricing").

Reading a unit is open to anyone at the store — a Seller has to be able to
look up the phone in a customer's hand — but the payload itself is
narrower without ``Cost.View`` (FR-1.7), so the permission shapes the
response rather than gating the route.

Writing is ``Pricing.Set``: Owner/Manager only, because *"a Storekeeper
should not see margins or set prices"* (§2). The practical consequence is
worth stating plainly — a Seller who scans an unpriced used handset at the
counter cannot fix it themselves, which is why the resolution error names
who can (FR-4.2b).

There is no route that creates a unit. Handsets enter stock through a
Goods Receipt (M4) or a stock count's unexpected list (M6); a unit that
could be conjured directly would be one with no movement behind it, which
§4.3 rule 1 forbids.
"""

from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends

from application.commands.change_device_unit_condition import (
    ChangeDeviceUnitConditionCommand,
    ChangeDeviceUnitConditionHandler,
)
from application.commands.reprice_device_unit import (
    RepriceDeviceUnitCommand,
    RepriceDeviceUnitHandler,
)
from application.commands.reprice_device_units import (
    RepriceDeviceUnitsCommand,
    RepriceDeviceUnitsHandler,
)
from application.core import ResultWithData
from application.dtos import CurrentUser
from application.models import DeviceUnitData, PriceChangeData
from application.queries.get_device_unit import GetDeviceUnitHandler, GetDeviceUnitQuery
from application.queries.get_device_unit_price_history import (
    GetDeviceUnitPriceHistoryHandler,
    GetDeviceUnitPriceHistoryQuery,
)
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/device-units",
    tags=["stock"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.post("/price")
async def reprice_device_units(
    body: RepriceDeviceUnitsCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[RepriceDeviceUnitsHandler],
) -> ResultWithData[int]:
    """Bulk markdown (FR-2.21) — atomic: one bad unit writes nothing.

    Declared before ``/{device_unit_id}`` so "price" is not matched as a
    UUID path segment.
    """
    require(current, Permission.PRICING_SET)
    return await handler.handle(body)


@router.get("/{device_unit_id}")
async def get_device_unit(
    device_unit_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetDeviceUnitHandler],
) -> ResultWithData[DeviceUnitData]:
    require(current, Permission.CATALOG_VIEW)
    return await handler.handle(GetDeviceUnitQuery(device_unit_id=device_unit_id))


@router.get("/{device_unit_id}/price-history")
async def get_device_unit_price_history(
    device_unit_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetDeviceUnitPriceHistoryHandler],
) -> ResultWithData[list[PriceChangeData]]:
    require(current, Permission.PRICING_SET)
    return await handler.handle(
        GetDeviceUnitPriceHistoryQuery(device_unit_id=device_unit_id)
    )


@router.patch("/{device_unit_id}/price")
async def reprice_device_unit(
    device_unit_id: UUID,
    body: RepriceDeviceUnitCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[RepriceDeviceUnitHandler],
) -> ResultWithData[DeviceUnitData]:
    require(current, Permission.PRICING_SET)
    return await handler.handle(body.model_copy(update={"device_unit_id": device_unit_id}))


@router.patch("/{device_unit_id}/condition")
async def change_device_unit_condition(
    device_unit_id: UUID,
    body: ChangeDeviceUnitConditionCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ChangeDeviceUnitConditionHandler],
) -> ResultWithData[DeviceUnitData]:
    """FR-2.18: condition is a pricing input, so it moves under the
    pricing permission rather than the catalog one."""
    require(current, Permission.PRICING_SET)
    return await handler.handle(body.model_copy(update={"device_unit_id": device_unit_id}))
