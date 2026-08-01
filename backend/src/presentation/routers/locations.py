"""Where this store keeps stock (PRD §8): read for anyone, write for a
Manager (``Permission.Location.*``, §2.1)."""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query

from application.commands.create_location import CreateLocationCommand, CreateLocationHandler
from application.commands.update_location import UpdateLocationCommand, UpdateLocationHandler
from application.core import PagedResult, ResultWithData
from application.dtos import CurrentUser
from application.queries.get_location import (
    GetLocationHandler,
    GetLocationQuery,
    LocationData,
)
from application.queries.list_locations import ListLocationsHandler, ListLocationsQuery
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/locations",
    tags=["catalog"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.get("")
async def list_locations(
    query: Annotated[ListLocationsQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListLocationsHandler],
) -> PagedResult[LocationData]:
    require(current, Permission.LOCATION_VIEW)
    return await handler.handle(query)


@router.post("", status_code=201)
async def create_location(
    body: CreateLocationCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CreateLocationHandler],
) -> ResultWithData[LocationData]:
    require(current, Permission.LOCATION_MANAGE)
    return await handler.handle(body)


@router.get("/{location_id}")
async def get_location(
    location_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetLocationHandler],
) -> ResultWithData[LocationData]:
    require(current, Permission.LOCATION_VIEW)
    return await handler.handle(GetLocationQuery(location_id=location_id))


@router.patch("/{location_id}")
async def update_location(
    location_id: UUID,
    body: UpdateLocationCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UpdateLocationHandler],
) -> ResultWithData[LocationData]:
    require(current, Permission.LOCATION_MANAGE)
    return await handler.handle(body.model_copy(update={"location_id": location_id}))
