"""One accessory whose weighted-average cost has reached its catalog price
(FR-2.19), attached to a Goods Receipt confirm response.

Not behind ``Permission.Cost.View``: the point is that whoever confirms the
receipt sees the mismatch. These figures are a comparison the store needs,
not the receipt's own line costs.
"""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from application.dtos import BelowCostAlert
from application.models.money import MoneyData


class BelowCostAlertData(CamelModel):
    product_id: UUID
    sku: str
    catalog_price: MoneyData
    average_unit_cost: MoneyData

    @classmethod
    def from_entity(cls, alert: BelowCostAlert) -> BelowCostAlertData:
        return cls(
            product_id=alert.product_id,
            sku=alert.sku,
            catalog_price=MoneyData.from_entity(alert.catalog_price),
            average_unit_cost=MoneyData.from_entity(alert.average_unit_cost),
        )
