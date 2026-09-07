"""One handset in the device-inventory list, and the status a caller filters by.

A read row, not an entity: the list flattens the unit, its catalog row and its
location, the same way ``AgeingRow`` does.

``DeviceInventoryStatusFilter`` is not ``DeviceStatus``. A handset a customer
brought back is ``IN_STOCK`` again (§4.3), so "returned by a customer" is a
derived fact read from the presence of a ``CUSTOMER_RETURN`` movement, not a
status value.

``resolved_price`` restates FR-2.14: the unit's own asking price wins, else the
catalog price, but only for a ``NEW`` unit. ``catalog_price`` is carried on the
row so the rule can run here without re-loading the product.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from domain.enums import DeviceCondition, DeviceStatus, DocumentType
from domain.value_objects import Money


class DeviceInventoryStatusFilter(StrEnum):
    IN_STOCK = "in_stock"
    SOLD = "sold"
    CUSTOMER_RETURNED = "customer_returned"
    RETURNED_TO_SUPPLIER = "returned_to_supplier"
    WRITTEN_OFF = "written_off"
    RECEIPT_CANCELLED = "receipt_cancelled"


@dataclass(frozen=True, slots=True)
class DeviceInventoryRow:
    device_unit_id: UUID
    imei: str
    imei2: str | None
    serial_number: str | None
    product_id: UUID
    sku: str
    product_name: str
    brand: str | None
    condition: DeviceCondition
    status: DeviceStatus
    was_customer_returned: bool
    location_id: UUID | None
    location_name: str | None
    created_at: datetime
    acquisition_cost: Money
    asking_price: Money | None
    catalog_price: Money | None
    source_document_type: DocumentType | None
    source_document_id: UUID | None

    @property
    def resolved_price(self) -> Money | None:
        if self.asking_price is not None:
            return self.asking_price
        if self.condition is DeviceCondition.NEW:
            return self.catalog_price
        return None

    @property
    def implied_margin(self) -> Money | None:
        price = self.resolved_price
        return None if price is None else price - self.acquisition_cost
