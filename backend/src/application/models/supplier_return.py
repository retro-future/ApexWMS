"""Response payload for a Supplier Return — PRD §5.5, §8.

The nested line class lives here rather than in its own module: it is one
branch of this payload's tree, never returned on its own by anything.

**No money anywhere on it**, and that is deliberate rather than an
omission. What a return is worth is the goods' book value — a handset's own
cost, an accessory's share of a replayed cost pool — and neither is a
column on the document (see the migration). Computing one would mean a
repository read inside a ``from_entity``, which is not what a response
mapper does; and storing one would be a second opinion about a figure the
financial ledger already holds. The value the store was credited is a
``SUPPLIER_RETURN_CREDIT`` row, and M8's reporting is where it is read.

A consequence worth stating: nothing here is behind ``Permission.Cost.View``,
because there is no cost on it to hide.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from domain.entities import SupplierReturn, SupplierReturnLine
from domain.enums import DocumentStatus, SupplierReturnReason, TrackingType
from domain.value_objects import Currency


class SupplierReturnLineData(CamelModel):
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
    def from_entity(cls, line: SupplierReturnLine) -> SupplierReturnLineData:
        return cls(
            id=line.id,
            product_id=line.product_id,
            device_unit_id=line.device_unit_id,
            imei=line.imei,
            quantity=line.quantity,
            currency=line.currency,
            tracking_type=line.tracking_type,
        )


class SupplierReturnData(CamelModel):
    id: UUID
    number: str
    status: DocumentStatus
    supplier_id: UUID
    location_id: UUID
    reason: SupplierReturnReason
    note: str | None
    created_by: UUID
    created_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    lines: list[SupplierReturnLineData]
    # The running count §6 wants after every beep, so the operator never has
    # to count the list themselves.
    line_count: int

    @classmethod
    def from_entity(cls, document: SupplierReturn) -> SupplierReturnData:
        return cls(
            id=document.id,
            number=document.number,
            status=document.status,
            supplier_id=document.supplier_id,
            location_id=document.location_id,
            reason=document.reason,
            note=document.note,
            created_by=document.created_by,
            created_at=document.created_at,
            confirmed_at=document.confirmed_at,
            cancelled_at=document.cancelled_at,
            cancellation_reason=document.cancellation_reason,
            lines=[SupplierReturnLineData.from_entity(line) for line in document.lines],
            line_count=len(document.lines),
        )
