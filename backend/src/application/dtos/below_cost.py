"""One accessory carried at or above its catalog price, at one location (FR-2.19).

A read row, not an entity: the report flattens the catalog row, the level
and the location, and its cost is a pool the ledger implies, not a column.
"""

from dataclasses import dataclass
from uuid import UUID

from domain.value_objects import Currency, Money


@dataclass(frozen=True, slots=True)
class BelowCostRow:
    product_id: UUID
    sku: str
    product_name: str
    location_id: UUID
    location_name: str
    quantity: int
    currency: Currency
    catalog_price: Money
    average_unit_cost: Money

    @property
    def shortfall(self) -> Money:
        return self.average_unit_cost - self.catalog_price
