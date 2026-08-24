"""Response payload for a Write-Off — PRD §5.6, §8.

The same shape as ``SupplierReturnData`` against its own document, and
carrying no money for the same reason: the loss is the goods' book value,
which lives in the financial ledger as a ``WRITE_OFF_LOSS`` row rather than
on the document (see the migration).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from domain.entities import WriteOff, WriteOffLine
from domain.enums import DocumentStatus, TrackingType, WriteOffReason
from domain.value_objects import Currency


class WriteOffLineData(CamelModel):
    id: UUID
    product_id: UUID
    device_unit_id: UUID | None
    # None on a quantity line. It is here rather than only the unit id
    # because unscanning names the IMEI (§6) — the operator is holding the
    # phone, not its primary key.
    imei: str | None
    quantity: int
    currency: Currency
    tracking_type: TrackingType

    @classmethod
    def from_entity(cls, line: WriteOffLine) -> WriteOffLineData:
        return cls(
            id=line.id,
            product_id=line.product_id,
            device_unit_id=line.device_unit_id,
            imei=line.imei,
            quantity=line.quantity,
            currency=line.currency,
            tracking_type=line.tracking_type,
        )


class WriteOffData(CamelModel):
    id: UUID
    number: str
    status: DocumentStatus
    location_id: UUID
    reason: WriteOffReason
    note: str | None
    created_by: UUID
    created_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    lines: list[WriteOffLineData]
    line_count: int

    @classmethod
    def from_entity(cls, document: WriteOff) -> WriteOffData:
        return cls(
            id=document.id,
            number=document.number,
            status=document.status,
            location_id=document.location_id,
            reason=document.reason,
            note=document.note,
            created_by=document.created_by,
            created_at=document.created_at,
            confirmed_at=document.confirmed_at,
            cancelled_at=document.cancelled_at,
            cancellation_reason=document.cancellation_reason,
            lines=[WriteOffLineData.from_entity(line) for line in document.lines],
            line_count=len(document.lines),
        )
