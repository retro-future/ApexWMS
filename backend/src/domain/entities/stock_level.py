"""``(product, location) → quantity``, for QUANTITY products only (§4.2).

**A projection, never a source of truth.** It is derived from
``stock_movements`` and updated in the same transaction as the movement
that causes it — never edited independently, and always rebuildable by
summing the ledger. ``verify-projections`` does exactly that and reports
any level that disagrees.

Serialized products have no row here: a phone's whereabouts is its own
``DeviceUnit.location_id``, which is the same projection at the grain the
tracking type demands (§4.1). Nobody serializes a box of 200 screen
protectors, and nobody counts iPhones by the box.
"""

from dataclasses import dataclass
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.errors import InvalidMovementError


@dataclass(eq=False, kw_only=True)
class StockLevel(UuidEntity, TenantEntity):
    product_id: UUID
    location_id: UUID
    quantity: int

    def __post_init__(self) -> None:
        # A negative level means the ledger says the store issued goods it
        # never received. That is a real condition worth surfacing, but it
        # is never a state to persist: FR-4.7 refuses a confirm that would
        # oversell rather than booking the shortfall.
        if self.quantity < 0:
            raise InvalidMovementError(
                f"stock level would go to {self.quantity} — a location cannot hold "
                "less than nothing"
            )
