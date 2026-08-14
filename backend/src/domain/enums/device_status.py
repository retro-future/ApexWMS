"""Where a handset is in its life (PRD §4.2).

A **projection** of ``stock_movements``, never a field anyone assigns on
its own (§4.3 rule 1): a unit becomes ``SOLD`` because a sale wrote a
movement, and it comes back to ``IN_STOCK`` because a cancellation wrote
the compensating one. ``verify-projections`` recomputes every value here
from the ledger and reports any that disagree.

``RESERVED`` exists from the start even though reservations are v2: a
draft invoice holding a unit is the shape it will take, and a status
value costs nothing until then.
"""

from enum import StrEnum


class DeviceStatus(StrEnum):
    IN_STOCK = "in_stock"
    RESERVED = "reserved"
    SOLD = "sold"
    RETURNED_TO_SUPPLIER = "returned_to_supplier"
    WRITTEN_OFF = "written_off"
    # Where a handset lands when the Goods Receipt that brought it in is
    # cancelled (§4.4). It was not destroyed and it was not sent back under
    # a supplier return, so neither of those is true of it — and calling it
    # WRITTEN_OFF would make the write-off report count a loss the store
    # never took.
    RECEIPT_CANCELLED = "receipt_cancelled"

    @property
    def is_on_hand(self) -> bool:
        """Whether the store still physically holds the unit.

        On-hand inventory value sums exactly these (§4.6), and only these
        may be repriced (FR-2.16) — one definition, so the two cannot
        drift apart.
        """
        return self in _ON_HAND


_ON_HAND = frozenset({DeviceStatus.IN_STOCK, DeviceStatus.RESERVED})
