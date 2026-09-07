"""One row of the device-inventory list — FR-9.1, PRD §5.9.

Cost and implied margin are omitted without ``Permission.Cost.View`` (FR-1.7),
the same shaping ``AgeingRowData`` does. ``resolvedPrice`` is what the unit
would sell at (FR-2.14) and stays on every row, because that is what a Seller
reads.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from application.core import CamelModel
from application.dtos import DeviceInventoryRow
from domain.enums import DeviceCondition, DeviceStatus, DocumentType
from domain.value_objects import Currency


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
    currency: Currency
    asking_price: Decimal | None
    asking_price_minor: int | None
    resolved_price: Decimal | None
    resolved_price_minor: int | None
    source_document_type: DocumentType | None
    source_document_id: UUID | None
    # --- Permission.Cost.View only (FR-1.7) ---
    acquisition_cost: Decimal | None = None
    acquisition_cost_minor: int | None = None
    implied_margin: Decimal | None = None
    implied_margin_minor: int | None = None

    @classmethod
    def from_entity(
        cls, row: DeviceInventoryRow, now: datetime, *, show_cost: bool
    ) -> DeviceInventoryRowData:
        resolved = row.resolved_price
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
            currency=row.acquisition_cost.currency,
            asking_price=row.asking_price.as_major() if row.asking_price else None,
            asking_price_minor=(
                row.asking_price.amount_minor if row.asking_price else None
            ),
            resolved_price=resolved.as_major() if resolved else None,
            resolved_price_minor=resolved.amount_minor if resolved else None,
            source_document_type=row.source_document_type,
            source_document_id=row.source_document_id,
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
