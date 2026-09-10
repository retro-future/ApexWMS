"""One row of the ageing report — FR-9.4, PRD §5.9.

Cost and implied margin are omitted entirely without ``Permission.Cost.View``
(FR-1.7). What survives that omission is the asking price and the markdown
count, which is what makes the report still readable to someone who may not
see money: *this handset has been cut twice and is still here.*
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.dtos import AgeingRow
from application.models.money import MoneyData
from domain.enums import DeviceCondition


class AgeingRowData(CamelModel):
    device_unit_id: UUID
    imei: str
    product_id: UUID
    sku: str
    product_name: str
    brand: str | None
    condition: DeviceCondition
    location_id: UUID | None
    location_name: str | None
    since: datetime
    days_in_stock: int
    asking_price: MoneyData | None
    markdown_count: int
    # --- Permission.Cost.View only (FR-1.7) ---
    acquisition_cost: MoneyData | None = None
    implied_margin: MoneyData | None = None

    @classmethod
    def from_entity(
        cls, row: AgeingRow, now: datetime, *, show_cost: bool
    ) -> AgeingRowData:
        data = cls(
            device_unit_id=row.device_unit_id,
            imei=row.imei,
            product_id=row.product_id,
            sku=row.sku,
            product_name=row.product_name,
            brand=row.brand,
            condition=row.condition,
            location_id=row.location_id,
            location_name=row.location_name,
            since=row.created_at,
            days_in_stock=(now - row.created_at).days,
            asking_price=MoneyData.from_entity(row.asking_price),
            markdown_count=row.markdown_count,
        )
        if not show_cost:
            return data
        return data.model_copy(
            update={
                "acquisition_cost": MoneyData.from_entity(row.acquisition_cost),
                "implied_margin": MoneyData.from_entity(row.implied_margin),
            }
        )
