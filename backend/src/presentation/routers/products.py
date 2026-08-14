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
from application.commands.update_product import (
    UpdateProductCommand,
    UpdateProductCommandPayload,
    UpdateProductHandler,
)
from application.core import PagedResult, ResultWithData
from application.dtos import CurrentUser
from application.models import PriceChangeData, ProductData
from application.queries.get_product import GetProductHandler, GetProductQuery
from application.queries.get_product_price_history import (
    GetProductPriceHistoryHandler,
    GetProductPriceHistoryQuery,
)
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
    require(current, Permission.CATALOG_VIEW)
    return await handler.handle(query)


@router.post("", status_code=201)
async def create_product(
    body: CreateProductCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CreateProductHandler],
) -> ResultWithData[ProductData]:
    require(current, Permission.CATALOG_MANAGE)
    if body.default_sale_price is not None:
        require(current, Permission.PRICING_SET)
    return await handler.handle(body)


@router.get("/{product_id}")
async def get_product(
    product_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetProductHandler],
) -> ResultWithData[ProductData]:
    require(current, Permission.CATALOG_VIEW)
    return await handler.handle(GetProductQuery(product_id=product_id))


@router.get("/{product_id}/price-history")
async def get_product_price_history(
    product_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetProductPriceHistoryHandler],
) -> ResultWithData[list[PriceChangeData]]:
    # What a model has cost over time is margin-adjacent: §2.1 keeps a
    # Storekeeper and a Seller out of pricing history for the same reason
    # it keeps them out of cost.
    require(current, Permission.PRICING_SET)
    return await handler.handle(GetProductPriceHistoryQuery(product_id=product_id))


@router.patch("/{product_id}")
async def update_product(
    product_id: UUID,
    body: UpdateProductCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UpdateProductHandler],
) -> ResultWithData[ProductData]:
    require(current, Permission.CATALOG_MANAGE)
    # A price change is its own act under its own permission (FR-2.19),
    # separable from renaming a product or deactivating it.
    if "default_sale_price" in body.model_fields_set:
        require(current, Permission.PRICING_SET)
    return await handler.handle(
        UpdateProductCommand(**body.model_dump(exclude_unset=True), product_id=product_id)
    )
