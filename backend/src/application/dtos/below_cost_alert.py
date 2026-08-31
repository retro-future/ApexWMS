"""One accessory whose weighted-average cost has reached or passed its
catalog price (FR-2.19). A carrier for a confirm-response row, built from
the ``Product`` and its replayed ``CostPool``."""

from dataclasses import dataclass
from uuid import UUID

from domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class BelowCostAlert:
    product_id: UUID
    sku: str
    catalog_price: Money
    average_unit_cost: Money
