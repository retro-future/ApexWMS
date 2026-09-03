"""What the store has on order (PRD §8, FR-3.1, FR-3.2, FR-3.9).

``Permission.PurchaseOrder.*`` belongs to Manager and Owner alone (§2.1),
which is why nothing here shapes its response by permission the way the
receipt routes do: everyone who can read a PO can already see costs, and
an order with the money removed would be an empty document rather than a
safe one.

There is no route that edits a line's product or quantity. A draft order
that is wrong there is cancelled and raised again — nothing has been
scanned onto it, so nothing is lost. Price is the one exception: a line may
be raised with none, since the store may not know it yet, so there is one
route that fills it in (FR-3.1). Price stays optional through confirm — an
order may be confirmed with unpriced lines and the cost set later on the
Goods Receipt.
"""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query, Response

from application.commands.cancel_purchase_order import (
    CancelPurchaseOrderCommand,
    CancelPurchaseOrderCommandPayload,
    CancelPurchaseOrderHandler,
)
from application.commands.confirm_purchase_order import (
    ConfirmPurchaseOrderCommand,
    ConfirmPurchaseOrderHandler,
)
from application.commands.create_purchase_order import (
    CreatePurchaseOrderCommand,
    CreatePurchaseOrderHandler,
)
from application.commands.price_purchase_order_line import (
    PricePurchaseOrderLineCommand,
    PricePurchaseOrderLineCommandPayload,
    PricePurchaseOrderLineHandler,
)
from application.core import PagedResult, ResultWithData
from application.dtos import CurrentUser
from application.models import PurchaseOrderData
from application.queries.get_purchase_order import (
    GetPurchaseOrderHandler,
    GetPurchaseOrderQuery,
)
from application.queries.get_purchase_order_pdf import (
    GetPurchaseOrderPdfHandler,
    GetPurchaseOrderPdfQuery,
)
from application.queries.list_purchase_orders import (
    ListPurchaseOrdersHandler,
    ListPurchaseOrdersQuery,
)
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/purchase-orders",
    tags=["inbound"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.get("")
async def list_purchase_orders(
    query: Annotated[ListPurchaseOrdersQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListPurchaseOrdersHandler],
) -> PagedResult[PurchaseOrderData]:
    require(current, Permission.PURCHASE_ORDER_VIEW)
    return await handler.handle(query)


@router.post("", status_code=201)
async def create_purchase_order(
    body: CreatePurchaseOrderCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CreatePurchaseOrderHandler],
) -> ResultWithData[PurchaseOrderData]:
    require(current, Permission.PURCHASE_ORDER_MANAGE)
    return await handler.handle(body)


@router.get("/{purchase_order_id}")
async def get_purchase_order(
    purchase_order_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetPurchaseOrderHandler],
) -> ResultWithData[PurchaseOrderData]:
    require(current, Permission.PURCHASE_ORDER_VIEW)
    return await handler.handle(
        GetPurchaseOrderQuery(purchase_order_id=purchase_order_id)
    )


@router.get("/{purchase_order_id}/pdf", response_class=Response)
async def get_purchase_order_pdf(
    purchase_order_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetPurchaseOrderPdfHandler],
) -> Response:
    """FR-3.2, FR-8.1: the order on paper, with the store's letterhead.

    ``COST_VIEW`` on top of the order's own read permission: this page is a
    list of unit costs, and saying so beats resting on the fact that
    everyone holding ``PurchaseOrder.View`` happens to hold both today.
    """
    require(current, Permission.PURCHASE_ORDER_VIEW, Permission.COST_VIEW)
    result = await handler.handle(
        GetPurchaseOrderPdfQuery(purchase_order_id=purchase_order_id)
    )
    assert result.data is not None
    rendered = result.data
    return Response(
        content=rendered.content,
        media_type=rendered.content_type,
        headers={"Content-Disposition": f'inline; filename="{rendered.filename}"'},
    )


@router.patch("/{purchase_order_id}/lines/{line_id}")
async def price_purchase_order_line(
    purchase_order_id: UUID,
    line_id: UUID,
    body: PricePurchaseOrderLineCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[PricePurchaseOrderLineHandler],
) -> ResultWithData[PurchaseOrderData]:
    """FR-3.1: fills in a line's price once the deal is agreed."""
    require(current, Permission.PURCHASE_ORDER_MANAGE)
    return await handler.handle(
        PricePurchaseOrderLineCommand(
            **body.model_dump(exclude_unset=True),
            purchase_order_id=purchase_order_id,
            line_id=line_id,
        )
    )


@router.post("/{purchase_order_id}/confirm")
async def confirm_purchase_order(
    purchase_order_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ConfirmPurchaseOrderHandler],
) -> ResultWithData[PurchaseOrderData]:
    """FR-3.2: fixes the order's numbers. It does not change stock."""
    require(current, Permission.PURCHASE_ORDER_MANAGE)
    return await handler.handle(
        ConfirmPurchaseOrderCommand(purchase_order_id=purchase_order_id)
    )


@router.post("/{purchase_order_id}/cancel")
async def cancel_purchase_order(
    purchase_order_id: UUID,
    body: CancelPurchaseOrderCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CancelPurchaseOrderHandler],
) -> ResultWithData[PurchaseOrderData]:
    require(current, Permission.DOCUMENT_CANCEL)
    return await handler.handle(
        CancelPurchaseOrderCommand(
            **body.model_dump(exclude_unset=True), purchase_order_id=purchase_order_id
        )
    )
