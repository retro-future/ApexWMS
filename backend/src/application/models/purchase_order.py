"""Response payload for a Purchase Order — PRD §5.3, FR-3.9.

No cost shaping here, unlike the receipt: `Permission.PurchaseOrder.View`
belongs to Manager and Owner alone (§2.1), and both always hold
`Permission.Cost.View`. A PO *is* a statement of what the store agreed to
pay, so a version of it with the money removed would be an empty document
rather than a safe one.

``fulfilment`` is FR-3.9's pending / partial / complete, derived on read by
comparing what was ordered against what confirmed receipts actually
brought in. It is not stored: a stored copy would be one more projection
to keep honest, and this one is a comparison of two things already
recorded.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from application.core import CamelModel
from application.models.money import MoneyData
from domain.entities import PurchaseOrder, PurchaseOrderLine
from domain.enums import DocumentStatus, TrackingType
from domain.value_objects import Currency


class Fulfilment(StrEnum):
    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETE = "complete"


class PurchaseOrderLineData(CamelModel):
    id: UUID
    product_id: UUID
    quantity: int
    tracking_type: TrackingType
    currency: Currency
    # Null until an Owner or Manager prices the line (FR-3.1); the order
    # cannot be confirmed while either is still null.
    unit_cost: MoneyData | None
    total_cost: MoneyData | None
    received_quantity: int

    @classmethod
    def from_entity(
        cls, line: PurchaseOrderLine, received: int
    ) -> PurchaseOrderLineData:
        return cls(
            id=line.id,
            product_id=line.product_id,
            quantity=line.quantity,
            tracking_type=line.tracking_type,
            currency=line.currency,
            unit_cost=MoneyData.from_entity(line.unit_cost),
            total_cost=MoneyData.from_entity(line.total_cost),
            received_quantity=received,
        )


class PurchaseOrderData(CamelModel):
    id: UUID
    number: str
    status: DocumentStatus
    supplier_id: UUID
    note: str | None
    created_by: UUID
    created_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    lines: list[PurchaseOrderLineData]
    # One figure per currency present, never their sum (FR-2.7).
    subtotals: list[MoneyData]
    fulfilment: Fulfilment

    @classmethod
    def from_entity(
        cls, order: PurchaseOrder, received: dict[UUID, int]
    ) -> PurchaseOrderData:
        return cls(
            id=order.id,
            number=order.number,
            status=order.status,
            supplier_id=order.supplier_id,
            note=order.note,
            created_by=order.created_by,
            created_at=order.created_at,
            confirmed_at=order.confirmed_at,
            cancelled_at=order.cancelled_at,
            lines=[
                PurchaseOrderLineData.from_entity(line, received.get(line.product_id, 0))
                for line in order.lines
            ],
            subtotals=MoneyData.from_entity(order.subtotals()),
            fulfilment=cls._fulfilment(order.ordered_quantities(), received),
        )

    @staticmethod
    def _fulfilment(ordered: dict[UUID, int], received: dict[UUID, int]) -> Fulfilment:
        if not any(received.get(product, 0) for product in ordered):
            return Fulfilment.PENDING
        if all(received.get(product, 0) >= count for product, count in ordered.items()):
            return Fulfilment.COMPLETE
        return Fulfilment.PARTIAL
