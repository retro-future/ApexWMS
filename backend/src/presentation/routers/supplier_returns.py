"""Sending goods back to a supplier, IMEI by IMEI (PRD §8, §5.5, §6).

Owner and Manager only, both to read and to write (§2.1). There is no
Storekeeper path here, unlike receiving: deciding that stock goes back to a
supplier is a commercial call, not a stockroom one.

Cancelling takes ``Document.Cancel`` rather than ``SupplierReturn.Manage``,
so the permission that reverses two ledgers is the same one everywhere
(§4.3 rule 2).
"""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query

from application.commands.cancel_supplier_return import (
    CancelSupplierReturnCommand,
    CancelSupplierReturnCommandPayload,
    CancelSupplierReturnHandler,
)
from application.commands.confirm_supplier_return import (
    ConfirmSupplierReturnCommand,
    ConfirmSupplierReturnHandler,
)
from application.commands.create_supplier_return import (
    CreateSupplierReturnCommand,
    CreateSupplierReturnHandler,
)
from application.commands.scan_supplier_return_line import (
    ScanSupplierReturnLineCommand,
    ScanSupplierReturnLineCommandPayload,
    ScanSupplierReturnLineHandler,
)
from application.commands.unscan_supplier_return_line import (
    UnscanSupplierReturnLineCommand,
    UnscanSupplierReturnLineHandler,
)
from application.core import PagedResult, Result, ResultWithData
from application.dtos import CurrentUser
from application.models import SupplierReturnData
from application.queries.get_supplier_return import (
    GetSupplierReturnHandler,
    GetSupplierReturnQuery,
)
from application.queries.list_supplier_returns import (
    ListSupplierReturnsHandler,
    ListSupplierReturnsQuery,
)
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/supplier-returns",
    tags=["returns"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.get("")
async def list_supplier_returns(
    query: Annotated[ListSupplierReturnsQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListSupplierReturnsHandler],
) -> PagedResult[SupplierReturnData]:
    require(current, Permission.SUPPLIER_RETURN_VIEW)
    return await handler.handle(query)


@router.post("", status_code=201)
async def create_supplier_return(
    body: CreateSupplierReturnCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CreateSupplierReturnHandler],
) -> ResultWithData[SupplierReturnData]:
    """FR-5.1: names the supplier, the location and why the goods are going back."""
    require(current, Permission.SUPPLIER_RETURN_MANAGE)
    return await handler.handle(body)


@router.get("/{supplier_return_id}")
async def get_supplier_return(
    supplier_return_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetSupplierReturnHandler],
) -> ResultWithData[SupplierReturnData]:
    require(current, Permission.SUPPLIER_RETURN_VIEW)
    return await handler.handle(
        GetSupplierReturnQuery(supplier_return_id=supplier_return_id)
    )


@router.post("/{supplier_return_id}/scan")
async def scan_supplier_return_line(
    supplier_return_id: UUID,
    body: ScanSupplierReturnLineCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ScanSupplierReturnLineHandler],
) -> ResultWithData[SupplierReturnData]:
    """FR-5.2: a handset that is not on the shelf is refused on the scan that
    named it, while the operator is still holding it."""
    require(current, Permission.SUPPLIER_RETURN_MANAGE)
    return await handler.handle(
        ScanSupplierReturnLineCommand(
            **body.model_dump(exclude_unset=True),
            supplier_return_id=supplier_return_id,
        )
    )


@router.delete("/{supplier_return_id}/scan/{imei}")
async def unscan_supplier_return_line(
    supplier_return_id: UUID,
    imei: str,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UnscanSupplierReturnLineHandler],
) -> Result:
    require(current, Permission.SUPPLIER_RETURN_MANAGE)
    return await handler.handle(
        UnscanSupplierReturnLineCommand(
            supplier_return_id=supplier_return_id, imei=imei
        )
    )


@router.post("/{supplier_return_id}/confirm")
async def confirm_supplier_return(
    supplier_return_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ConfirmSupplierReturnHandler],
) -> ResultWithData[SupplierReturnData]:
    """FR-5.3: marks the handsets returned and books the credit, together."""
    require(current, Permission.SUPPLIER_RETURN_MANAGE)
    return await handler.handle(
        ConfirmSupplierReturnCommand(supplier_return_id=supplier_return_id)
    )


@router.post("/{supplier_return_id}/cancel")
async def cancel_supplier_return(
    supplier_return_id: UUID,
    body: CancelSupplierReturnCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CancelSupplierReturnHandler],
) -> ResultWithData[SupplierReturnData]:
    """Compensates both ledgers (§4.3 rule 2). The original rows stay."""
    require(current, Permission.DOCUMENT_CANCEL)
    return await handler.handle(
        CancelSupplierReturnCommand(
            **body.model_dump(exclude_unset=True),
            supplier_return_id=supplier_return_id,
        )
    )
