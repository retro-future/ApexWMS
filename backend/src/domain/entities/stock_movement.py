"""The backbone of the system (PRD §4.3).

Every single change to stock — every receipt, sale, write-off, count
adjustment, supplier return — is an immutable row here. Three rules, none
of them negotiable:

1. **Nothing mutates stock except by writing a movement.** There is no
   code path that sets a stock level to 5. There is only "write a movement
   of +2, and the projection follows".
2. **Movements are never deleted or updated.** Cancelling a confirmed
   document writes *compensating* movements in the opposite direction. The
   history of the mistake is part of the history.
3. **Every movement names its cause** (``document_type`` + ``document_id``)
   and **its author** (``user_id``).

What this buys: *"how did this IMEI end up here, and who touched it?"* is
one table ordered by time. Auditability is not a feature added later; it
is a consequence of the shape of the data.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.enums import DocumentType, MovementType
from domain.errors import InvalidMovementError


@dataclass(eq=False, kw_only=True)
class StockMovement(UuidEntity, TenantEntity):
    occurred_at: datetime
    movement_type: MovementType
    product_id: UUID
    # Set for a SERIAL line, null for a QUANTITY one — the two tracking
    # types write to the same ledger (§4.1), and this is the only column
    # that tells them apart.
    device_unit_id: UUID | None = None
    location_id: UUID
    quantity_delta: int
    document_type: DocumentType
    document_id: UUID
    user_id: UUID
    note: str | None = None

    def __post_init__(self) -> None:
        if self.quantity_delta == 0:
            raise InvalidMovementError(
                "a movement of zero records nothing — the ledger holds what changed"
            )
        # A serialized movement is one handset. Two would mean the row could
        # not say *which* unit it meant, and the IMEI trace rests on it being
        # able to.
        if self.device_unit_id is not None and abs(self.quantity_delta) != 1:
            raise InvalidMovementError(
                f"a movement naming one device unit moves one unit, not "
                f"{self.quantity_delta}"
            )

    def reversed(self, occurred_at: datetime, user_id: UUID) -> StockMovement:
        """The compensating movement for this one (§4.3 rule 2).

        Same type, same cause, opposite direction — the type is kept
        because a reversal of a sale is still part of the sale's story, and
        an excluded-from-reports "reversal" category would silently make a
        cancelled sale count as a sale wherever someone forgot it.
        """
        return StockMovement(
            occurred_at=occurred_at,
            movement_type=self.movement_type,
            product_id=self.product_id,
            device_unit_id=self.device_unit_id,
            location_id=self.location_id,
            quantity_delta=-self.quantity_delta,
            document_type=self.document_type,
            document_id=self.document_id,
            user_id=user_id,
            note=f"reversal of movement {self.id}",
        )
