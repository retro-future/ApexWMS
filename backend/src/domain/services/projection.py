"""What the stock ledger implies — PRD §4.3.

Stock levels and device statuses are **projections**: derived from
``stock_movements``, updated in the same transaction as the movement that
causes them, and never edited independently. Which means there has to be
exactly one statement of what "derived" means, or the code that maintains
the projection and the code that audits it can disagree — and then
``verify-projections`` reports drift that is really just two opinions.

This module is that statement. The posting service applies it forward as
movements arrive; ``verify-projections`` applies it to a unit's whole
history and compares. Same function, so a mismatch is always real.

Pure: a sequence of movements in, a state out. No repository, no I/O.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import UUID

from domain.enums import DeviceStatus, MovementType

if TYPE_CHECKING:
    # Deferred for the same reason as domain/services/pricing.py: a runtime
    # import here would make domain.entities and domain.services import
    # each other. Only used as a type hint below, never constructed.
    from domain.entities import StockMovement

# Where a handset ends up when a movement takes it off the shelf.
#
# ``COUNT_ADJUSTMENT`` maps to ``WRITTEN_OFF`` because a negative count
# adjustment *is* the finding that a unit is missing (FR-6.4), and §4.6
# books its book value as a loss.
#
# ``RECEIPT`` only ever goes negative as the compensation for a cancelled
# Goods Receipt — a unit that should never have entered stock. It gets its
# own terminal state rather than borrowing ``WRITTEN_OFF``: the store lost
# nothing, and a write-off report that counted these would be reporting
# losses that never happened.
_STATUS_WHEN_GONE: dict[MovementType, DeviceStatus] = {
    MovementType.SALE: DeviceStatus.SOLD,
    MovementType.WRITE_OFF: DeviceStatus.WRITTEN_OFF,
    MovementType.SUPPLIER_RETURN: DeviceStatus.RETURNED_TO_SUPPLIER,
    MovementType.COUNT_ADJUSTMENT: DeviceStatus.WRITTEN_OFF,
    MovementType.RECEIPT: DeviceStatus.RECEIPT_CANCELLED,
}


class UnitProjector:
    """Turns a movement history into what it implies right now.

    Stateless: every method is a pure function of the movements passed in,
    grouped here so ``LedgerPoster`` and ``ProjectionVerifier`` can both
    take one as a constructor dependency (PRD §7.3) instead of importing
    module-level functions directly.
    """

    @staticmethod
    def net_quantity(movements: Sequence[StockMovement]) -> int:
        """The level a sequence of movements implies.

        A plain sum, and that is the point: because a reversal is a
        movement of the opposite sign rather than a separate category
        (§4.3 rule 2), no caller has to know which rows to exclude.
        """
        return sum(movement.quantity_delta for movement in movements)

    @staticmethod
    def project(movements: Sequence[StockMovement]) -> tuple[DeviceStatus, UUID | None]:
        """Where one handset is, according to its own timeline.

        *movements* must be that unit's history in chronological order.
        Returns the status and the location it belongs at — ``None`` once
        the unit has left the store, which is the invariant ``DeviceUnit``
        itself enforces.

        ``RESERVED`` is never produced here: holding a unit for an open
        draft is not a stock event and writes no movement, so it cannot be
        a conclusion drawn from the ledger.
        """
        if not movements:
            raise ValueError("a unit with no movements has no ledger state to project")

        if UnitProjector.net_quantity(movements) > 0:
            # The last movement that put it somewhere is where it is: a
            # compensating +1 undoes the sale that took it off the shelf,
            # and returns it to the location that movement named.
            latest_arrival = next(m for m in reversed(movements) if m.quantity_delta > 0)
            return DeviceStatus.IN_STOCK, latest_arrival.location_id

        latest_departure = next(m for m in reversed(movements) if m.quantity_delta < 0)
        return _STATUS_WHEN_GONE[latest_departure.movement_type], None
