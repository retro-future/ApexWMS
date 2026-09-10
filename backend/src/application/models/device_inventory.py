"""One row of the device-inventory list — FR-9.1, PRD §5.9.

Cost and implied margin are omitted without ``Permission.Cost.View`` (FR-1.7),
the same shaping ``AgeingRowData`` does. ``resolvedPrice`` is what the unit
would sell at (FR-2.14) and stays on every row, because that is what a Seller
reads.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.dtos import DeviceInventoryRow
from application.models.money import MoneyData
from domain.enums import DeviceCondition, DeviceStatus, DocumentType


class DeviceInventoryRowData(CamelModel):
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
    since: datetime
    days_in_stock: int
    asking_price: MoneyData | None
    resolved_price: MoneyData | None
    source_document_type: DocumentType | None
    source_document_id: UUID | None
    # --- Permission.Cost.View only (FR-1.7) ---
    acquisition_cost: MoneyData | None = None
    implied_margin: MoneyData | None = None

    @classmethod
    def from_entity(
        cls, row: DeviceInventoryRow, now: datetime, *, show_cost: bool
    ) -> DeviceInventoryRowData:
        data = cls(
            device_unit_id=row.device_unit_id,
            imei=row.imei,
            imei2=row.imei2,
            serial_number=row.serial_number,
            product_id=row.product_id,
            sku=row.sku,
            product_name=row.product_name,
            brand=row.brand,
            condition=row.condition,
            status=row.status,
            was_customer_returned=row.was_customer_returned,
            location_id=row.location_id,
            location_name=row.location_name,
            since=row.created_at,
            days_in_stock=(now - row.created_at).days,
            asking_price=MoneyData.from_entity(row.asking_price),
            resolved_price=MoneyData.from_entity(row.resolved_price),
            source_document_type=row.source_document_type,
            source_document_id=row.source_document_id,
        )
        if not show_cost:
            return data
        return data.model_copy(
            update={
                "acquisition_cost": MoneyData.from_entity(row.acquisition_cost),
                "implied_margin": MoneyData.from_entity(row.implied_margin),
            }
        )
