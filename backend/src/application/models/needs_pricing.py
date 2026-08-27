"""One row of the needs-pricing worklist — FR-9.6, PRD §5.9.

No cost anywhere on it, on purpose. The list exists so an Owner or Manager
can price a handset before a Seller meets it at the counter, and what they
need for that is the model, the condition and how long it has been sitting
unsellable — not what the store paid.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.dtos import NeedsPricingReason, NeedsPricingRow
from domain.enums import DeviceCondition


class NeedsPricingRowData(CamelModel):
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
    days_unpriced: int
    reason: NeedsPricingReason

    @classmethod
    def from_entity(cls, row: NeedsPricingRow, now: datetime) -> NeedsPricingRowData:
        return cls(
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
            days_unpriced=(now - row.created_at).days,
            reason=row.reason,
        )
