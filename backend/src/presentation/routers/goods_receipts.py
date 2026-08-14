"""Receiving goods, IMEI by IMEI (PRD §8, §5.3, §6).

The permission split here is the workflow, not decoration (§2.1):

- ``Receiving.*`` is held by Storekeeper, Manager and Owner. A Seller
  cannot open or confirm a receipt.
- ``Pricing.Set`` is Manager and Owner only, and it guards the two places
  money is stated: the pricing route, and any cost or price sent on a
  scan. A Storekeeper scans an IMEI and a condition and nothing else
  (FR-3.4b).
- Reads are shaped by ``Cost.View`` inside the handler, so a Storekeeper's
  copy of the receipt carries asking prices and no costs at all (FR-1.7).

The practical consequence, stated rather than discovered: a delivery
containing used handsets needs an Owner or Manager to price it before it
can be confirmed (§4.5b, FR-3.10).
"""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query

from application.commands.cancel_goods_receipt import (
    CancelGoodsReceiptCommand,
    CancelGoodsReceiptCommandPayload,
    CancelGoodsReceiptHandler,
)
from application.commands.confirm_goods_receipt import (
    ConfirmGoodsReceiptCommand,
    ConfirmGoodsReceiptHandler,
)
from application.commands.create_goods_receipt import (
    CreateGoodsReceiptCommand,
    CreateGoodsReceiptHandler,
)
from application.commands.price_receipt_unit import (
    PriceReceiptUnitCommand,
    PriceReceiptUnitCommandPayload,
    PriceReceiptUnitHandler,
)
from application.commands.scan_receipt_unit import (
    ScanReceiptUnitCommand,
    ScanReceiptUnitCommandPayload,
    ScanReceiptUnitHandler,
)
from application.commands.unscan_receipt_unit import (
    UnscanReceiptUnitCommand,
    UnscanReceiptUnitHandler,
)
from application.core import PagedResult, Result, ResultWithData
from application.dtos import CurrentUser
from application.models import GoodsReceiptData, ReceivedUnitData, ScanResultData
from application.queries.get_goods_receipt import (
    GetGoodsReceiptHandler,
    GetGoodsReceiptQuery,
)
from application.queries.list_goods_receipts import (
    ListGoodsReceiptsHandler,
    ListGoodsReceiptsQuery,
)
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/receipts",
    tags=["inbound"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)

# The scan body's money fields, which escalate the route's permission.
_PRICING_FIELDS = frozenset(
    {"acquisition_cost", "asking_price", "cash_paid", "cash_paid_currency"}
)


@router.get("")
async def list_goods_receipts(
    query: Annotated[ListGoodsReceiptsQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListGoodsReceiptsHandler],
) -> PagedResult[GoodsReceiptData]:
    require(current, Permission.RECEIVING_VIEW)
    return await handler.handle(query)


@router.post("", status_code=201)
async def create_goods_receipt(
    body: CreateGoodsReceiptCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CreateGoodsReceiptHandler],
) -> ResultWithData[GoodsReceiptData]:
    """FR-3.3b: ``supplierId`` is required for ``SUPPLIER`` and rejected for
    ``TRADE_IN`` — the aggregate refuses either mistake."""
    require(current, Permission.RECEIVING_MANAGE)
    if any(line.unit_cost is not None for line in body.lines or []):
        require(current, Permission.PRICING_SET)
    return await handler.handle(body)


@router.get("/{goods_receipt_id}")
async def get_goods_receipt(
    goods_receipt_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetGoodsReceiptHandler],
) -> ResultWithData[GoodsReceiptData]:
    require(current, Permission.RECEIVING_VIEW)
    return await handler.handle(
        GetGoodsReceiptQuery(goods_receipt_id=goods_receipt_id)
    )


@router.post("/{goods_receipt_id}/scan")
async def scan_receipt_unit(
    goods_receipt_id: UUID,
    body: ScanReceiptUnitCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ScanReceiptUnitHandler],
) -> ResultWithData[ScanResultData]:
    """FR-3.4, FR-3.5: one beep. Malformed and duplicate IMEIs are rejected
    here, while the operator still has the phone in their hand."""
    require(current, Permission.RECEIVING_MANAGE)
    if _PRICING_FIELDS & body.model_fields_set:
        require(current, Permission.PRICING_SET)
    return await handler.handle(
        ScanReceiptUnitCommand(
            **body.model_dump(exclude_unset=True), goods_receipt_id=goods_receipt_id
        )
    )


@router.patch("/{goods_receipt_id}/scan/{imei}")
async def price_receipt_unit(
    goods_receipt_id: UUID,
    imei: str,
    body: PriceReceiptUnitCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[PriceReceiptUnitHandler],
) -> ResultWithData[ReceivedUnitData]:
    """FR-3.4b: an Owner or Manager prices what the Storekeeper scanned."""
    require(current, Permission.PRICING_SET)
    return await handler.handle(
        PriceReceiptUnitCommand(
            **body.model_dump(exclude_unset=True),
            goods_receipt_id=goods_receipt_id,
            imei=imei,
        )
    )


@router.delete("/{goods_receipt_id}/scan/{imei}")
async def unscan_receipt_unit(
    goods_receipt_id: UUID,
    imei: str,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UnscanReceiptUnitHandler],
) -> Result:
    require(current, Permission.RECEIVING_MANAGE)
    return await handler.handle(
        UnscanReceiptUnitCommand(goods_receipt_id=goods_receipt_id, imei=imei)
    )


@router.post("/{goods_receipt_id}/confirm")
async def confirm_goods_receipt(
    goods_receipt_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ConfirmGoodsReceiptHandler],
) -> ResultWithData[GoodsReceiptData]:
    """FR-3.7: creates the handsets and writes both ledgers, together."""
    require(current, Permission.RECEIVING_MANAGE)
    return await handler.handle(
        ConfirmGoodsReceiptCommand(goods_receipt_id=goods_receipt_id)
    )


@router.post("/{goods_receipt_id}/cancel")
async def cancel_goods_receipt(
    goods_receipt_id: UUID,
    body: CancelGoodsReceiptCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CancelGoodsReceiptHandler],
) -> ResultWithData[GoodsReceiptData]:
    """Compensates both ledgers (§4.3 rule 2). The original rows stay."""
    require(current, Permission.DOCUMENT_CANCEL)
    return await handler.handle(
        CancelGoodsReceiptCommand(
            **body.model_dump(exclude_unset=True), goods_receipt_id=goods_receipt_id
        )
    )
