"""One row of the below-cost report (FR-2.19, PRD §5.9).

No ``Permission.Cost.View`` gate: the report *is* the cost picture, so
trimming its figures would leave an empty table.
"""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from application.dtos import BelowCostRow
from application.models.money import MoneyData


class BelowCostRowData(CamelModel):
    product_id: UUID
    sku: str
    product_name: str
    location_id: UUID
    location_name: str
    quantity: int
    catalog_price: MoneyData
    average_unit_cost: MoneyData
    shortfall: MoneyData

    @classmethod
    def from_entity(cls, row: BelowCostRow) -> BelowCostRowData:
        return cls(
            product_id=row.product_id,
            sku=row.sku,
            product_name=row.product_name,
            location_id=row.location_id,
            location_name=row.location_name,
            quantity=row.quantity,
            catalog_price=MoneyData.from_entity(row.catalog_price),
            average_unit_cost=MoneyData.from_entity(row.average_unit_cost),
            shortfall=MoneyData.from_entity(row.shortfall),
        )
