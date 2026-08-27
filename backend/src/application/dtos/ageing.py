"""One handset that has not moved — FR-9.4, PRD §5.9.

Dead stock is the phone retailer's core financial risk, and the sharpest
form of it is a used handset cut twice that is still on the shelf. That is
why ``markdown_count`` is on the row: it counts genuine reductions only,
never the first pricing, which is not evidence of anything.

``implied_margin`` is derived rather than selected, so the subtraction runs
through ``Money`` and a USD asking price can never be netted against a som
cost.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.enums import DeviceCondition
from domain.value_objects import Money


@dataclass(frozen=True, slots=True)
class AgeingRow:
    device_unit_id: UUID
    imei: str
    product_id: UUID
    sku: str
    product_name: str
    brand: str | None
    condition: DeviceCondition
    location_id: UUID | None
    location_name: str | None
    created_at: datetime
    acquisition_cost: Money
    asking_price: Money | None
    markdown_count: int

    @property
    def implied_margin(self) -> Money | None:
        """None where the unit carries no asking price — an unpriced handset
        has no margin to imply, and zero would read as one."""
        if self.asking_price is None:
            return None
        return self.asking_price - self.acquisition_cost
