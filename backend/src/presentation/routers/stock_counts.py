"""Counting the shelf against the books (PRD §8, §5.6, §6).

**The permission split here is the whole workflow** (§2.1, FR-6.4). A
Storekeeper opens a count, scans it and closes it — they are the person who
walks the aisles. Only an Owner or Manager confirms it, because agreeing to
write off what is missing is a different decision from reporting that it is
missing, and the two should not be the same person.

``Pricing.Set`` escalates the scan when the body carries an
``acquisitionCost``, exactly as it does on a Goods Receipt: stating what a
surprise handset cost is stating money, and a Storekeeper does not. They
scan the phone anyway and somebody with the permission fills in the figure
before the confirm (FR-6.4b).

Cancelling takes ``Document.Cancel``, so the permission that reverses two
ledgers is the same one everywhere.
"""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query

from application.commands.cancel_stock_count import (
    CancelStockCountCommand,
    CancelStockCountCommandPayload,
    CancelStockCountHandler,
)
from application.commands.close_stock_count import (
    CloseStockCountCommand,
    CloseStockCountHandler,
)
from application.commands.confirm_stock_count import (
    ConfirmStockCountCommand,
    ConfirmStockCountHandler,
)
from application.commands.count_stock_count_line import (
    CountStockCountLineCommand,
    CountStockCountLineCommandPayload,
    CountStockCountLineHandler,
)
from application.commands.open_stock_count import (
    OpenStockCountCommand,
    OpenStockCountHandler,
)
from application.commands.scan_stock_count_unit import (
    ScanStockCountUnitCommand,
    ScanStockCountUnitCommandPayload,
    ScanStockCountUnitHandler,
)
from application.commands.unscan_stock_count_unit import (
    UnscanStockCountUnitCommand,
    UnscanStockCountUnitHandler,
)
from application.core import PagedResult, Result, ResultWithData
from application.dtos import CurrentUser
from application.models import CountScanResultData, StockCountData
from application.queries.get_stock_count import GetStockCountHandler, GetStockCountQuery
from application.queries.list_stock_counts import (
    ListStockCountsHandler,
    ListStockCountsQuery,
)
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/stock-counts",
    tags=["counts"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.get("")
async def list_stock_counts(
    query: Annotated[ListStockCountsQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListStockCountsHandler],
) -> PagedResult[StockCountData]:
    require(current, Permission.STOCK_COUNT_RUN)
    return await handler.handle(query)


@router.post("", status_code=201)
async def open_stock_count(
    body: OpenStockCountCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[OpenStockCountHandler],
) -> ResultWithData[StockCountData]:
    """FR-6.1: snapshots what the books expect at this location, right now."""
    require(current, Permission.STOCK_COUNT_RUN)
    return await handler.handle(body)


@router.get("/{stock_count_id}")
async def get_stock_count(
    stock_count_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetStockCountHandler],
) -> ResultWithData[StockCountData]:
    """FR-6.3's discrepancy report: every row carries its own outcome, so
    there is no separate report to fetch."""
    require(current, Permission.STOCK_COUNT_RUN)
    return await handler.handle(GetStockCountQuery(stock_count_id=stock_count_id))


@router.post("/{stock_count_id}/scan")
async def scan_stock_count_unit(
    stock_count_id: UUID,
    body: ScanStockCountUnitCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ScanStockCountUnitHandler],
) -> ResultWithData[CountScanResultData]:
    """FR-6.2: an IMEI marks a handset present, a barcode bumps an
    accessory's tally. An IMEI the store has never seen is **accepted**, not
    refused — finding it is what the count is for (FR-6.3)."""
    require(current, Permission.STOCK_COUNT_RUN)
    if "acquisition_cost" in body.model_fields_set:
        require(current, Permission.PRICING_SET)
    return await handler.handle(
        ScanStockCountUnitCommand(
            **body.model_dump(exclude_unset=True), stock_count_id=stock_count_id
        )
    )


@router.delete("/{stock_count_id}/scan/{imei}")
async def unscan_stock_count_unit(
    stock_count_id: UUID,
    imei: str,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UnscanStockCountUnitHandler],
) -> Result:
    """An expected handset goes back to missing; an unexpected one is removed."""
    require(current, Permission.STOCK_COUNT_RUN)
    return await handler.handle(
        UnscanStockCountUnitCommand(stock_count_id=stock_count_id, imei=imei)
    )


@router.patch("/{stock_count_id}/lines/{line_id}")
async def count_stock_count_line(
    stock_count_id: UUID,
    line_id: UUID,
    body: CountStockCountLineCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CountStockCountLineHandler],
) -> ResultWithData[StockCountData]:
    """FR-6.2: the typed alternative to scanning each accessory. Zero is a
    real answer, and it is not the same as leaving the line uncounted."""
    require(current, Permission.STOCK_COUNT_RUN)
    return await handler.handle(
        CountStockCountLineCommand(
            **body.model_dump(exclude_unset=True),
            stock_count_id=stock_count_id,
            line_id=line_id,
        )
    )


@router.post("/{stock_count_id}/close")
async def close_stock_count(
    stock_count_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CloseStockCountHandler],
) -> ResultWithData[StockCountData]:
    """FR-6.3: freezes the count and reports it. Writes to neither ledger."""
    require(current, Permission.STOCK_COUNT_RUN)
    return await handler.handle(CloseStockCountCommand(stock_count_id=stock_count_id))


@router.post("/{stock_count_id}/confirm")
async def confirm_stock_count(
    stock_count_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ConfirmStockCountHandler],
) -> ResultWithData[StockCountData]:
    """FR-6.4: Owner and Manager only. Applies the adjustments and lets
    reality win."""
    require(current, Permission.STOCK_COUNT_CONFIRM)
    return await handler.handle(ConfirmStockCountCommand(stock_count_id=stock_count_id))


@router.post("/{stock_count_id}/cancel")
async def cancel_stock_count(
    stock_count_id: UUID,
    body: CancelStockCountCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CancelStockCountHandler],
) -> ResultWithData[StockCountData]:
    """Compensates both ledgers (§4.3 rule 2). The original rows stay."""
    require(current, Permission.DOCUMENT_CANCEL)
    return await handler.handle(
        CancelStockCountCommand(
            **body.model_dump(exclude_unset=True), stock_count_id=stock_count_id
        )
    )
