"""Selling, IMEI by IMEI (PRD §8, §5.4, §6).

The permission split here is the workflow, not decoration (§2.1):

- ``Sales.*`` is held by Seller, Manager and Owner. A Storekeeper cannot
  open or confirm an invoice.
- ``Pricing.Override`` is Manager and Owner only, and it guards exactly one
  thing: charging something other than what the system resolved. A Seller's
  invoice sells at the resolved price, unchanged (FR-4.5). The line route
  is open to a Seller for the quantity of an accessory, and escalates the
  moment the body mentions a price.
- ``Document.Cancel`` is Manager and Owner, because cancelling writes
  compensating rows into two ledgers (§4.4).

Nothing on this document is behind ``Cost.View``: every figure on an
invoice is a price the customer is being asked for, and a Seller must see
all of them (FR-1.7).
"""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query, Response

from application.commands.cancel_sales_invoice import (
    CancelSalesInvoiceCommand,
    CancelSalesInvoiceCommandPayload,
    CancelSalesInvoiceHandler,
)
from application.commands.confirm_sales_invoice import (
    ConfirmSalesInvoiceCommand,
    ConfirmSalesInvoiceHandler,
)
from application.commands.create_sales_invoice import (
    CreateSalesInvoiceCommand,
    CreateSalesInvoiceHandler,
)
from application.commands.override_invoice_line_price import (
    OverrideInvoiceLinePriceCommand,
    OverrideInvoiceLinePriceCommandPayload,
    OverrideInvoiceLinePriceHandler,
)
from application.commands.scan_invoice_line import (
    ScanInvoiceLineCommand,
    ScanInvoiceLineCommandPayload,
    ScanInvoiceLineHandler,
)
from application.commands.unscan_invoice_line import (
    UnscanInvoiceLineCommand,
    UnscanInvoiceLineHandler,
)
from application.core import PagedResult, ResultWithData
from application.dtos import CurrentUser
from application.models import InvoiceScanResultData, SalesInvoiceData
from application.queries.get_sales_invoice import (
    GetSalesInvoiceHandler,
    GetSalesInvoiceQuery,
)
from application.queries.get_sales_invoice_pdf import (
    GetSalesInvoicePdfHandler,
    GetSalesInvoicePdfQuery,
)
from application.queries.list_sales_invoices import (
    ListSalesInvoicesHandler,
    ListSalesInvoicesQuery,
)
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/invoices",
    tags=["outbound"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)

# The line body's money fields, which escalate the route's permission.
_PRICING_FIELDS = frozenset({"price", "note"})


@router.get("")
async def list_sales_invoices(
    query: Annotated[ListSalesInvoicesQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListSalesInvoicesHandler],
) -> PagedResult[SalesInvoiceData]:
    require(current, Permission.SALES_VIEW)
    return await handler.handle(query)


@router.post("", status_code=201)
async def create_sales_invoice(
    body: CreateSalesInvoiceCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CreateSalesInvoiceHandler],
) -> ResultWithData[SalesInvoiceData]:
    """FR-4.1: header only. Lines arrive by scan."""
    require(current, Permission.SALES_MANAGE)
    return await handler.handle(body)


@router.get("/{sales_invoice_id}")
async def get_sales_invoice(
    sales_invoice_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetSalesInvoiceHandler],
) -> ResultWithData[SalesInvoiceData]:
    require(current, Permission.SALES_VIEW)
    return await handler.handle(GetSalesInvoiceQuery(sales_invoice_id=sales_invoice_id))


@router.post("/{sales_invoice_id}/scan")
async def scan_invoice_line(
    sales_invoice_id: UUID,
    body: ScanInvoiceLineCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ScanInvoiceLineHandler],
) -> ResultWithData[InvoiceScanResultData]:
    """FR-4.2: one beep. A handset that is sold, elsewhere, or unpriced is
    refused here, while the customer is still standing there."""
    require(current, Permission.SALES_MANAGE)
    return await handler.handle(
        ScanInvoiceLineCommand(
            **body.model_dump(exclude_unset=True), sales_invoice_id=sales_invoice_id
        )
    )


@router.patch("/{sales_invoice_id}/lines/{line_id}")
async def override_invoice_line_price(
    sales_invoice_id: UUID,
    line_id: UUID,
    body: OverrideInvoiceLinePriceCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[OverrideInvoiceLinePriceHandler],
) -> ResultWithData[SalesInvoiceData]:
    """FR-4.5: only an Owner or Manager may charge something other than the
    resolved price, and the override is stamped with their name."""
    require(current, Permission.SALES_MANAGE)
    if _PRICING_FIELDS & body.model_fields_set:
        require(current, Permission.PRICING_OVERRIDE)
    return await handler.handle(
        OverrideInvoiceLinePriceCommand(
            **body.model_dump(exclude_unset=True),
            sales_invoice_id=sales_invoice_id,
            line_id=line_id,
        )
    )


@router.delete("/{sales_invoice_id}/lines/{line_id}")
async def unscan_invoice_line(
    sales_invoice_id: UUID,
    line_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UnscanInvoiceLineHandler],
) -> ResultWithData[SalesInvoiceData]:
    require(current, Permission.SALES_MANAGE)
    return await handler.handle(
        UnscanInvoiceLineCommand(sales_invoice_id=sales_invoice_id, line_id=line_id)
    )


@router.post("/{sales_invoice_id}/confirm")
async def confirm_sales_invoice(
    sales_invoice_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ConfirmSalesInvoiceHandler],
) -> ResultWithData[SalesInvoiceData]:
    """FR-4.6: re-resolves every price, marks the handsets sold, and writes
    both ledgers, together."""
    require(current, Permission.SALES_MANAGE)
    return await handler.handle(
        ConfirmSalesInvoiceCommand(sales_invoice_id=sales_invoice_id)
    )


@router.post("/{sales_invoice_id}/cancel")
async def cancel_sales_invoice(
    sales_invoice_id: UUID,
    body: CancelSalesInvoiceCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CancelSalesInvoiceHandler],
) -> ResultWithData[SalesInvoiceData]:
    """FR-4.8: compensates both ledgers. The original rows stay."""
    require(current, Permission.DOCUMENT_CANCEL)
    return await handler.handle(
        CancelSalesInvoiceCommand(
            **body.model_dump(exclude_unset=True), sales_invoice_id=sales_invoice_id
        )
    )


@router.get("/{sales_invoice_id}/pdf", response_class=Response)
async def get_sales_invoice_pdf(
    sales_invoice_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetSalesInvoicePdfHandler],
) -> Response:
    """FR-8.1: the sale on paper, with the store's letterhead and the IMEI.

    Rendered on demand rather than served from storage — a confirmed
    invoice is immutable, so the file is the same every time. A draft is
    refused: it holds no prices to print (FR-4.5b1).
    """
    require(current, Permission.SALES_VIEW)
    result = await handler.handle(
        GetSalesInvoicePdfQuery(sales_invoice_id=sales_invoice_id)
    )
    assert result.data is not None
    rendered = result.data
    return Response(
        content=rendered.content,
        media_type=rendered.content_type,
        headers={"Content-Disposition": f'inline; filename="{rendered.filename}"'},
    )
