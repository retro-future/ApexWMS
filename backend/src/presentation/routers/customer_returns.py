"""Taking goods back from a customer, IMEI by IMEI (PRD §8, §5.4b, §6).

Owner and Manager only, both to read and to write (§2.1). There is no
Seller path here even though a Seller may sell: handing money back is the
same kind of call as a supplier return, a write-off or a cancellation, and
§2.1 reserves all of them.

Two escalations on top of that base. Lowering a refund takes
``Pricing.Override``, the same permission that discounts a sale, because
keeping part of a customer's money is the same act in the other direction.
Cancelling takes ``Document.Cancel``, so the permission that reverses two
ledgers is the same one everywhere (§4.3 rule 2).
"""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query

from application.commands.cancel_customer_return import (
    CancelCustomerReturnCommand,
    CancelCustomerReturnCommandPayload,
    CancelCustomerReturnHandler,
)
from application.commands.confirm_customer_return import (
    ConfirmCustomerReturnCommand,
    ConfirmCustomerReturnCommandPayload,
    ConfirmCustomerReturnHandler,
)
from application.commands.create_customer_return import (
    CreateCustomerReturnCommand,
    CreateCustomerReturnHandler,
)
from application.commands.scan_customer_return_line import (
    ScanCustomerReturnLineCommand,
    ScanCustomerReturnLineCommandPayload,
    ScanCustomerReturnLineHandler,
)
from application.commands.set_customer_return_refund import (
    SetCustomerReturnRefundCommand,
    SetCustomerReturnRefundCommandPayload,
    SetCustomerReturnRefundHandler,
)
from application.commands.unscan_customer_return_line import (
    UnscanCustomerReturnLineCommand,
    UnscanCustomerReturnLineHandler,
)
from application.core import PagedResult, Result, ResultWithData
from application.dtos import CurrentUser
from application.models import CustomerReturnData
from application.queries.get_customer_return import (
    GetCustomerReturnHandler,
    GetCustomerReturnQuery,
)
from application.queries.list_customer_returns import (
    ListCustomerReturnsHandler,
    ListCustomerReturnsQuery,
)
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/customer-returns",
    tags=["returns"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)

# Lowering the refund is a pricing decision, not a return one, so a body
# that names either of these escalates. Same shape as the invoice router's
# ``_PRICING_FIELDS``.
_REFUND_FIELDS = frozenset({"refund", "note"})


@router.get("")
async def list_customer_returns(
    query: Annotated[ListCustomerReturnsQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListCustomerReturnsHandler],
) -> PagedResult[CustomerReturnData]:
    require(current, Permission.CUSTOMER_RETURN_VIEW)
    return await handler.handle(query)


@router.post("", status_code=201)
async def create_customer_return(
    body: CreateCustomerReturnCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CreateCustomerReturnHandler],
) -> ResultWithData[CustomerReturnData]:
    """FR-4.9: names the sale being unwound, where the goods land, and why."""
    require(current, Permission.CUSTOMER_RETURN_MANAGE)
    return await handler.handle(body)


@router.get("/{customer_return_id}")
async def get_customer_return(
    customer_return_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetCustomerReturnHandler],
) -> ResultWithData[CustomerReturnData]:
    require(current, Permission.CUSTOMER_RETURN_VIEW)
    return await handler.handle(
        GetCustomerReturnQuery(customer_return_id=customer_return_id)
    )


@router.post("/{customer_return_id}/scan")
async def scan_customer_return_line(
    customer_return_id: UUID,
    body: ScanCustomerReturnLineCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ScanCustomerReturnLineHandler],
) -> ResultWithData[CustomerReturnData]:
    """FR-4.9a: goods this sale never sold are refused on the scan that named
    them, while the customer is still at the counter."""
    require(current, Permission.CUSTOMER_RETURN_MANAGE)
    return await handler.handle(
        ScanCustomerReturnLineCommand(
            **body.model_dump(exclude_unset=True),
            customer_return_id=customer_return_id,
        )
    )


@router.delete("/{customer_return_id}/scan/{imei}")
async def unscan_customer_return_line(
    customer_return_id: UUID,
    imei: str,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UnscanCustomerReturnLineHandler],
) -> Result:
    require(current, Permission.CUSTOMER_RETURN_MANAGE)
    return await handler.handle(
        UnscanCustomerReturnLineCommand(
            customer_return_id=customer_return_id, imei=imei
        )
    )


@router.patch("/{customer_return_id}/lines/{line_id}")
async def set_customer_return_refund(
    customer_return_id: UUID,
    line_id: UUID,
    body: SetCustomerReturnRefundCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[SetCustomerReturnRefundHandler],
) -> ResultWithData[CustomerReturnData]:
    """FR-4.9c: correct the count, or keep part of the price and sign for it."""
    require(current, Permission.CUSTOMER_RETURN_MANAGE)
    if body.model_fields_set & _REFUND_FIELDS:
        require(current, Permission.PRICING_OVERRIDE)
    return await handler.handle(
        SetCustomerReturnRefundCommand(
            **body.model_dump(exclude_unset=True),
            customer_return_id=customer_return_id,
            line_id=line_id,
        )
    )


@router.post("/{customer_return_id}/confirm")
async def confirm_customer_return(
    customer_return_id: UUID,
    body: ConfirmCustomerReturnCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ConfirmCustomerReturnHandler],
) -> ResultWithData[CustomerReturnData]:
    """FR-4.9f: puts the goods back and books the refund, together."""
    require(current, Permission.CUSTOMER_RETURN_MANAGE)
    return await handler.handle(
        ConfirmCustomerReturnCommand(
            **body.model_dump(exclude_unset=True),
            customer_return_id=customer_return_id,
        )
    )


@router.post("/{customer_return_id}/cancel")
async def cancel_customer_return(
    customer_return_id: UUID,
    body: CancelCustomerReturnCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CancelCustomerReturnHandler],
) -> ResultWithData[CustomerReturnData]:
    """Compensates both ledgers (§4.3 rule 2). The original rows stay."""
    require(current, Permission.DOCUMENT_CANCEL)
    return await handler.handle(
        CancelCustomerReturnCommand(
            **body.model_dump(exclude_unset=True),
            customer_return_id=customer_return_id,
        )
    )
