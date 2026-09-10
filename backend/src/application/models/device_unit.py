"""Response payload for one handset — PRD §8, FR-1.7, FR-7.2.

``DeviceUnitData`` omits cost, margin and ``cashPaid`` for anyone without
``Permission.Cost.View``. **This is response-shaping, not UI hiding**
(FR-1.7): a Storekeeper or a Seller who reads this endpoint never receives
the figures at all, so there is nothing in the payload for a curious
client to render.

The price it *would* sell at is always present, because that is what the
Seller actually needs at the counter (FR-7.2) — and where the resolution
rule refuses (a used handset nobody has priced), it says so explicitly
rather than reporting zero or the catalog price.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.models.money import MoneyData
from domain.entities import DeviceUnit, Product
from domain.enums import DeviceCondition, DeviceStatus
from domain.services import PriceResolver
from domain.value_objects import Currency


class DeviceUnitData(CamelModel):
    id: UUID
    imei: str
    imei2: str | None
    serial_number: str | None
    product_id: UUID
    sku: str
    product_name: str
    status: DeviceStatus
    condition: DeviceCondition
    location_id: UUID | None
    currency: Currency
    # The resolved price (FR-2.14), or None where the rule refuses. A
    # Seller reads this; ``resolvedPrice is None`` is the counter's cue
    # that an Owner or Manager has to price the handset first.
    asking_price: MoneyData | None
    resolved_price: MoneyData | None
    created_at: datetime
    # --- Permission.Cost.View only (FR-1.7) ---
    acquisition_cost: MoneyData | None = None
    # "paid 4 200 000 so'm · booked at $330" — a string, never a number,
    # so no caller can add it to anything (§4.5b, FR-3.4d).
    cash_paid: str | None = None

    @classmethod
    def from_entity(
        cls, unit: DeviceUnit, product: Product, *, show_cost: bool
    ) -> DeviceUnitData:
        resolved = PriceResolver.resolve_or_none(unit, product)
        data = cls(
            id=unit.id,
            imei=str(unit.imei),
            imei2=str(unit.imei2) if unit.imei2 else None,
            serial_number=unit.serial_number,
            product_id=unit.product_id,
            sku=str(product.sku),
            product_name=product.name,
            status=unit.status,
            condition=unit.condition,
            location_id=unit.location_id,
            currency=unit.currency,
            asking_price=MoneyData.from_entity(unit.asking_price),
            resolved_price=MoneyData.from_entity(resolved),
            created_at=unit.created_at,
        )
        if not show_cost:
            return data
        return data.model_copy(
            update={
                "acquisition_cost": MoneyData.from_entity(unit.acquisition_cost),
                "cash_paid": unit.cash_paid_display(),
            }
        )
