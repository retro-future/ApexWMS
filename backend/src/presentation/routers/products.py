"""The catalog (PRD §8): read for anyone at the store, write for a Manager.

``Catalog.View`` sits in every tenant role's permission set — a Seller
cannot sell what they cannot look up — while ``Catalog.Manage`` is
Owner/Manager only (§2.1).

There is no ``DELETE``: FR-2.4 deactivates and preserves history, which is
a ``PATCH`` with ``isActive: false``.
"""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query

from application.commands.create_product import CreateProductCommand, CreateProductHandler
from application.commands.update_product import UpdateProductCommand, UpdateProductHandler
from application.core import PagedResult, ResultWithData
from application.dtos import CurrentUser
from application.queries.get_product import GetProductHandler, GetProductQuery, ProductData
from application.queries.list_products import ListProductsHandler, ListProductsQuery
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/products",
    tags=["catalog"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.get("")
async def list_products(
    query: Annotated[ListProductsQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListProductsHandler],
) -> PagedResult[ProductData]:
    require(current, Permission.Catalog.View)
    return await handler.handle(query)


@router.post("", status_code=201)
async def create_product(
    body: CreateProductCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CreateProductHandler],
) -> ResultWithData[ProductData]:
    require(current, Permission.Catalog.Manage)
    return await handler.handle(body)


@router.get("/{product_id}")
async def get_product(
    product_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetProductHandler],
) -> ResultWithData[ProductData]:
    require(current, Permission.Catalog.View)
    return await handler.handle(GetProductQuery(product_id=product_id))


@router.patch("/{product_id}")
async def update_product(
    product_id: UUID,
    body: UpdateProductCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UpdateProductHandler],
) -> ResultWithData[ProductData]:
    require(current, Permission.Catalog.Manage)
    return await handler.handle(body.model_copy(update={"product_id": product_id}))
