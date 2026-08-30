"""What the shelves were worth at one instant, per location and currency.

Read from the ledgers rather than from ``device_units.status``, because the
month-end report asks the question about a moment that has passed and a
projection only ever answers it about now (§4.6, FR-10.6).
"""

from dataclasses import dataclass, field
from uuid import UUID

from domain.value_objects import CurrencyTotals, Money


@dataclass(frozen=True, slots=True)
class InventoryValueRow:
    """One ``(location, currency)`` subtotal, straight from SQL."""

    location_id: UUID
    location_name: str | None
    quantity: int
    amount: Money


@dataclass(frozen=True, slots=True)
class LocationInventoryValue:
    location_id: UUID
    location_name: str | None
    quantity: int = 0
    value: CurrencyTotals = field(default_factory=CurrencyTotals.empty)
