"""One row of the movement log — FR-9.5, PRD §5.9.

The raw stock ledger, so it shows quantities and not money: a movement
counts goods, and what the same event did to the till is a row in the other
report (FR-10.3). Nothing here is behind ``Permission.Cost.View`` because
there is no cost on it to hide.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.dtos import MovementLogRow
from domain.enums import DocumentType, MovementType


class MovementRowData(CamelModel):
    id: UUID
    occurred_at: datetime
    movement_type: MovementType
    # Signed: a reversal keeps its type and flips the sign (§4.3 rule 3).
    quantity_delta: int
    product_id: UUID
    sku: str
    product_name: str
    device_unit_id: UUID | None
    imei: str | None
    location_id: UUID
    location_name: str
    document_type: DocumentType
    document_id: UUID
    document_number: str | None
    user_id: UUID
    user_name: str | None
    note: str | None

    @classmethod
    def from_entity(cls, row: MovementLogRow) -> MovementRowData:
        return cls(
            id=row.id,
            occurred_at=row.occurred_at,
            movement_type=row.movement_type,
            quantity_delta=row.quantity_delta,
            product_id=row.product_id,
            sku=row.sku,
            product_name=row.product_name,
            device_unit_id=row.device_unit_id,
            imei=row.imei,
            location_id=row.location_id,
            location_name=row.location_name,
            document_type=row.document_type,
            document_id=row.document_id,
            document_number=row.document_number,
            user_id=row.actor.user_id,
            user_name=row.actor.user_name,
            note=row.note,
        )
