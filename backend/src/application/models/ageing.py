"""One row of the ageing report — FR-9.4, PRD §5.9.

Cost and implied margin are omitted entirely without ``Permission.Cost.View``
(FR-1.7). What survives that omission is the asking price and the markdown
count, which is what makes the report still readable to someone who may not
see money: *this handset has been cut twice and is still here.*
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from application.core import CamelModel
from application.dtos import AgeingRow
from domain.enums import DeviceCondition
from domain.value_objects import Currency


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
    currency: Currency
    asking_price: Decimal | None
    asking_price_minor: int | None
    markdown_count: int
    # --- Permission.Cost.View only (FR-1.7) ---
    acquisition_cost: Decimal | None = None
    acquisition_cost_minor: int | None = None
    implied_margin: Decimal | None = None
    implied_margin_minor: int | None = None

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
            currency=row.acquisition_cost.currency,
            asking_price=row.asking_price.as_major() if row.asking_price else None,
            asking_price_minor=(
                row.asking_price.amount_minor if row.asking_price else None
            ),
            markdown_count=row.markdown_count,
        )
        if not show_cost:
            return data
        margin = row.implied_margin
        return data.model_copy(
            update={
                "acquisition_cost": row.acquisition_cost.as_major(),
                "acquisition_cost_minor": row.acquisition_cost.amount_minor,
                "implied_margin": margin.as_major() if margin else None,
                "implied_margin_minor": margin.amount_minor if margin else None,
            }
        )
