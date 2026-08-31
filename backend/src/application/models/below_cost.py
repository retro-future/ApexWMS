"""One row of the below-cost report (PRD §5.9).

No ``Permission.Cost.View`` gate: the report *is* the cost picture, so
trimming its figures would leave an empty table.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from application.core import CamelModel
from application.dtos import BelowCostRow


class BelowCostRowData(CamelModel):
    product_id: UUID
    sku: str
    product_name: str
    location_id: UUID
    location_name: str
    quantity: int
    catalog_price: Decimal
    catalog_price_minor: int
    average_unit_cost: Decimal
    average_unit_cost_minor: int
    shortfall: Decimal
    shortfall_minor: int

    @classmethod
    def from_entity(cls, row: BelowCostRow) -> BelowCostRowData:
        return cls(
            product_id=row.product_id,
            sku=row.sku,
            product_name=row.product_name,
            location_id=row.location_id,
            location_name=row.location_name,
            quantity=row.quantity,
            catalog_price=row.catalog_price.as_major(),
            catalog_price_minor=row.catalog_price.amount_minor,
            average_unit_cost=row.average_unit_cost.as_major(),
            average_unit_cost_minor=row.average_unit_cost.amount_minor,
            shortfall=row.shortfall.as_major(),
            shortfall_minor=row.shortfall.amount_minor,
        )
