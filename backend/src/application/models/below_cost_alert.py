"""One accessory whose weighted-average cost has reached its catalog price
(FR-2.19), attached to a Goods Receipt confirm response.

Not behind ``Permission.Cost.View``: the point is that whoever confirms the
receipt sees the mismatch. These figures are a comparison the store needs,
not the receipt's own line costs.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from application.core import CamelModel
from application.dtos import BelowCostAlert


class BelowCostAlertData(CamelModel):
    product_id: UUID
    sku: str
    catalog_price: Decimal
    catalog_price_minor: int
    average_unit_cost: Decimal
    average_unit_cost_minor: int

    @classmethod
    def from_entity(cls, alert: BelowCostAlert) -> BelowCostAlertData:
        return cls(
            product_id=alert.product_id,
            sku=alert.sku,
            catalog_price=alert.catalog_price.as_major(),
            catalog_price_minor=alert.catalog_price.amount_minor,
            average_unit_cost=alert.average_unit_cost.as_major(),
            average_unit_cost_minor=alert.average_unit_cost.amount_minor,
        )
