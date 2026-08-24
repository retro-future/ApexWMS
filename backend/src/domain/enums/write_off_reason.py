"""Why stock was written off (PRD §5.6, FR-6.5).

Mandatory, and closed for the same reason ``SupplierReturnReason`` is: a
loss the store cannot categorise is a loss it cannot learn from. Theft and
damage call for very different responses, and telling them apart later
means telling them apart now.

A count shortage is **not** written here. It books ``COUNT_ADJUSTMENT``
under its own document (§4.6), even though the handset lands in the same
``WRITTEN_OFF`` status.
"""

from enum import StrEnum


class WriteOffReason(StrEnum):
    DAMAGE = "damage"
    LOSS = "loss"
    THEFT = "theft"
    OTHER = "other"
