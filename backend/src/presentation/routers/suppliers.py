"""Who this store buys from (PRD §8).

Suppliers have no permission module of their own — §2.1's matrix row reads
"Manage catalog (products, suppliers)", so they sit under
``Permission.Catalog.*`` alongside products. Reads therefore take
``Catalog.View``, which every tenant role holds: from M4 a Storekeeper
building a goods receipt has to pick the supplier it came from.
"""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Query

from application.commands.create_supplier import CreateSupplierCommand, CreateSupplierHandler
from application.commands.update_supplier import UpdateSupplierCommand, UpdateSupplierHandler
from application.core import PagedResult, ResultWithData
from application.dtos import CurrentUser
from application.queries.get_supplier import (
    GetSupplierHandler,
    GetSupplierQuery,
    SupplierData,
)
from application.queries.list_suppliers import ListSuppliersHandler, ListSuppliersQuery
from domain.permissions import Permission
from presentation.security import require

router = APIRouter(prefix="/suppliers", tags=["catalog"], route_class=DishkaRoute)


@router.get("")
async def list_suppliers(
    query: Annotated[ListSuppliersQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListSuppliersHandler],
) -> PagedResult[SupplierData]:
    require(current, Permission.Catalog.View)
    return await handler.handle(query)


@router.post("", status_code=201)
async def create_supplier(
    body: CreateSupplierCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CreateSupplierHandler],
) -> ResultWithData[SupplierData]:
    require(current, Permission.Catalog.Manage)
    return await handler.handle(body)


@router.get("/{supplier_id}")
async def get_supplier(
    supplier_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetSupplierHandler],
) -> ResultWithData[SupplierData]:
    require(current, Permission.Catalog.View)
    return await handler.handle(GetSupplierQuery(supplier_id=supplier_id))


@router.patch("/{supplier_id}")
async def update_supplier(
    supplier_id: UUID,
    body: UpdateSupplierCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UpdateSupplierHandler],
) -> ResultWithData[SupplierData]:
    require(current, Permission.Catalog.Manage)
    return await handler.handle(body.model_copy(update={"supplier_id": supplier_id}))
