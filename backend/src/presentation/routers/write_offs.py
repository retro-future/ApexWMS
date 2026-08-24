"""Writing stock off, IMEI by IMEI (PRD §8, §5.6, §6).

Owner and Manager only (§2.1). ``WriteOff.Manage`` guards the reads too:
§8's table grades the whole area as Manager, and a document whose only
purpose is to record a loss has no audience below that.

§8 lists this document as create-plus-confirm, without the scan pair. It
has them anyway, because §6's *"reject at scan time, not on submit"* is
stated as non-negotiable and a write-off is IMEI-driven like every other
document here — a Manager carrying five broken handsets should learn about
the wrong IMEI on the beep, not when they submit.
"""

from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query

from application.commands.cancel_write_off import (
    CancelWriteOffCommand,
    CancelWriteOffCommandPayload,
    CancelWriteOffHandler,
)
from application.commands.confirm_write_off import (
    ConfirmWriteOffCommand,
    ConfirmWriteOffHandler,
)
from application.commands.create_write_off import (
    CreateWriteOffCommand,
    CreateWriteOffHandler,
)
from application.commands.scan_write_off_line import (
    ScanWriteOffLineCommand,
    ScanWriteOffLineCommandPayload,
    ScanWriteOffLineHandler,
)
from application.commands.unscan_write_off_line import (
    UnscanWriteOffLineCommand,
    UnscanWriteOffLineHandler,
)
from application.core import PagedResult, Result, ResultWithData
from application.dtos import CurrentUser
from application.models import WriteOffData
from application.queries.get_write_off import GetWriteOffHandler, GetWriteOffQuery
from application.queries.list_write_offs import ListWriteOffsHandler, ListWriteOffsQuery
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/write-offs",
    tags=["write-offs"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.get("")
async def list_write_offs(
    query: Annotated[ListWriteOffsQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListWriteOffsHandler],
) -> PagedResult[WriteOffData]:
    """Filterable by ``reason``: "what did theft cost us" is the question
    FR-6.5's closed set exists to answer."""
    require(current, Permission.WRITE_OFF_MANAGE)
    return await handler.handle(query)


@router.post("", status_code=201)
async def create_write_off(
    body: CreateWriteOffCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CreateWriteOffHandler],
) -> ResultWithData[WriteOffData]:
    """FR-6.5: the reason is mandatory and is stated before anything is scanned."""
    require(current, Permission.WRITE_OFF_MANAGE)
    return await handler.handle(body)


@router.get("/{write_off_id}")
async def get_write_off(
    write_off_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetWriteOffHandler],
) -> ResultWithData[WriteOffData]:
    require(current, Permission.WRITE_OFF_MANAGE)
    return await handler.handle(GetWriteOffQuery(write_off_id=write_off_id))


@router.post("/{write_off_id}/scan")
async def scan_write_off_line(
    write_off_id: UUID,
    body: ScanWriteOffLineCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ScanWriteOffLineHandler],
) -> ResultWithData[WriteOffData]:
    require(current, Permission.WRITE_OFF_MANAGE)
    return await handler.handle(
        ScanWriteOffLineCommand(
            **body.model_dump(exclude_unset=True), write_off_id=write_off_id
        )
    )


@router.delete("/{write_off_id}/scan/{imei}")
async def unscan_write_off_line(
    write_off_id: UUID,
    imei: str,
    current: FromDishka[CurrentUser],
    handler: FromDishka[UnscanWriteOffLineHandler],
) -> Result:
    require(current, Permission.WRITE_OFF_MANAGE)
    return await handler.handle(
        UnscanWriteOffLineCommand(write_off_id=write_off_id, imei=imei)
    )


@router.post("/{write_off_id}/confirm")
async def confirm_write_off(
    write_off_id: UUID,
    current: FromDishka[CurrentUser],
    handler: FromDishka[ConfirmWriteOffHandler],
) -> ResultWithData[WriteOffData]:
    """FR-6.5: marks the handsets written off and books the loss, together."""
    require(current, Permission.WRITE_OFF_MANAGE)
    return await handler.handle(ConfirmWriteOffCommand(write_off_id=write_off_id))


@router.post("/{write_off_id}/cancel")
async def cancel_write_off(
    write_off_id: UUID,
    body: CancelWriteOffCommandPayload,
    current: FromDishka[CurrentUser],
    handler: FromDishka[CancelWriteOffHandler],
) -> ResultWithData[WriteOffData]:
    """The case this exists for is a handset written off as lost and then found."""
    require(current, Permission.DOCUMENT_CANCEL)
    return await handler.handle(
        CancelWriteOffCommand(
            **body.model_dump(exclude_unset=True), write_off_id=write_off_id
        )
    )
