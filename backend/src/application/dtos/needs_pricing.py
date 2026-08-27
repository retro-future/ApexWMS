"""One in-stock handset that FR-2.14 refuses to price (FR-9.6).

A read row, not an entity: the worklist is a flat table over the unit, its
catalog row and its location, and re-loading three aggregates per row to
flatten them again would be work done twice.

``reason`` is derived rather than selected, because the store cannot act on
the two cases the same way: a used handset needs its own price, while a new
one is waiting on a catalog price that will cover every unit of the model.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from domain.enums import DeviceCondition


class NeedsPricingReason(StrEnum):
    USED_NO_PRICE = "used_no_price"
    NO_CATALOG_PRICE = "no_catalog_price"


@dataclass(frozen=True, slots=True)
class NeedsPricingRow:
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

    @property
    def reason(self) -> NeedsPricingReason:
        if self.condition is not DeviceCondition.NEW:
            return NeedsPricingReason.USED_NO_PRICE
        return NeedsPricingReason.NO_CATALOG_PRICE
