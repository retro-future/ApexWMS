"""Response payload for a Goods Receipt — PRD §5.3, §8.

The nested line class lives here rather than in its own module: it is one
branch of this payload's tree, never returned on its own by anything.
``ReceivedUnitData`` *is* returned on its own — by the scan and pricing
routes — so it keeps its own file.

Every money figure in here is a **cost**, so the whole of it is behind
``Permission.Cost.View``: subtotals, line costs, and each handset's
acquisition cost. What a Storekeeper still sees is the receipt itself —
its lines, its counts, and each handset's asking price.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.dtos import BelowCostAlert
from application.models.below_cost_alert import BelowCostAlertData
from application.models.exchange_rate import ExchangeRateData
from application.models.money import MoneyData
from application.models.received_unit import ReceivedUnitData
from domain.entities import GoodsReceipt, GoodsReceiptLine
from domain.enums import AcquisitionSource, DocumentStatus, TrackingType
from domain.value_objects import Currency


class GoodsReceiptLineData(CamelModel):
    id: UUID
    product_id: UUID
    quantity: int
    tracking_type: TrackingType
    currency: Currency
    # Serialized lines: how many IMEIs are on the line so far against how
    # many it declares. The running count §6 wants after every beep.
    scanned_count: int
    units: list[ReceivedUnitData]
    # --- Permission.Cost.View only (FR-1.7) ---
    unit_cost: MoneyData | None = None

    @classmethod
    def from_entity(
        cls, line: GoodsReceiptLine, *, show_cost: bool
    ) -> GoodsReceiptLineData:
        data = cls(
            id=line.id,
            product_id=line.product_id,
            quantity=line.quantity,
            tracking_type=line.tracking_type,
            currency=line.currency,
            scanned_count=len(line.units),
            units=[
                ReceivedUnitData.from_entity(unit, line, show_cost=show_cost)
                for unit in line.units
            ],
        )
        if not show_cost or line.unit_cost is None:
            return data
        return data.model_copy(
            update={
                "unit_cost": MoneyData.from_entity(line.unit_cost),
            }
        )


class GoodsReceiptData(CamelModel):
    id: UUID
    number: str
    status: DocumentStatus
    acquisition_source: AcquisitionSource
    supplier_id: UUID | None
    customer_id: UUID | None
    purchase_order_id: UUID | None
    location_id: UUID
    note: str | None
    created_by: UUID
    created_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    lines: list[GoodsReceiptLineData]
    # --- Permission.Cost.View only (FR-1.7) ---
    # One figure per currency present, never their sum (FR-2.7).
    subtotals: list[MoneyData] = []
    # Populated only by the confirm handler (see the below-cost design doc);
    # empty on get/list/create/cancel.
    below_cost_alerts: list[BelowCostAlertData] = []
    # The buying rate this trade-in was struck at (W9 B2). Read back only by
    # the detail query, which is the one screen that shows it.
    buyback_rate: ExchangeRateData | None = None

    @classmethod
    def from_entity(
        cls,
        receipt: GoodsReceipt,
        *,
        show_cost: bool,
        below_cost_alerts: list[BelowCostAlert] | None = None,
        buyback_rate: ExchangeRateData | None = None,
    ) -> GoodsReceiptData:
        alerts = [
            BelowCostAlertData.from_entity(one) for one in (below_cost_alerts or [])
        ]
        data = cls(
            id=receipt.id,
            number=receipt.number,
            status=receipt.status,
            acquisition_source=receipt.acquisition_source,
            supplier_id=receipt.supplier_id,
            customer_id=receipt.customer_id,
            purchase_order_id=receipt.purchase_order_id,
            location_id=receipt.location_id,
            note=receipt.note,
            created_by=receipt.created_by,
            created_at=receipt.created_at,
            confirmed_at=receipt.confirmed_at,
            cancelled_at=receipt.cancelled_at,
            lines=[
                GoodsReceiptLineData.from_entity(line, show_cost=show_cost)
                for line in receipt.lines
            ],
            below_cost_alerts=alerts,
            buyback_rate=buyback_rate,
        )
        if not show_cost:
            return data
        return data.model_copy(
            update={"subtotals": MoneyData.from_entity(receipt.subtotals())}
        )
