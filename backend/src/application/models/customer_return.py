"""Response payload for a Customer Return — PRD §5.4b, §8.

The nested line class lives here rather than in its own module: it is one
branch of this payload's tree, never returned on its own by anything.

**Money is on it, unlike the supplier return's payload**, and for the
reason that one gives in reverse: what a customer is paid back is not the
goods' book value but a price somebody agreed to, and the return stores it.
So the refund, the charge it is capped at, and the per-currency subtotals
are all plain fields here.

Nothing on it is behind ``Permission.Cost.View``. Every figure is a price
the customer is getting back, and what the goods *cost* is still absent —
that stays in the financial ledger, where M8's reporting reads it.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.models.money import MoneyData
from domain.entities import CustomerReturn, CustomerReturnLine
from domain.enums import CustomerReturnReason, DocumentStatus, TrackingType
from domain.value_objects import Currency


class CustomerReturnLineData(CamelModel):
    id: UUID
    sales_invoice_line_id: UUID
    product_id: UUID
    device_unit_id: UUID | None
    # None on a quantity line. It is here rather than only the unit id
    # because unscanning names the IMEI (§6) — the operator is holding the
    # phone, not its primary key.
    imei: str | None
    quantity: int
    # What the sale sold, so the screen can offer "return all" without a
    # second request.
    sold_quantity: int
    currency: Currency
    tracking_type: TrackingType
    charged_price: MoneyData
    refund_price: MoneyData
    line_total: MoneyData
    # Whether the store kept part of the price, and who signed for it.
    is_reduced: bool
    refund_approved_by: UUID | None
    refund_note: str | None

    @classmethod
    def from_entity(cls, line: CustomerReturnLine) -> CustomerReturnLineData:
        return cls(
            id=line.id,
            sales_invoice_line_id=line.sales_invoice_line_id,
            product_id=line.product_id,
            device_unit_id=line.device_unit_id,
            imei=line.imei,
            quantity=line.quantity,
            sold_quantity=line.sold_quantity,
            currency=line.currency,
            tracking_type=line.tracking_type,
            charged_price=MoneyData.from_entity(line.charged_price),
            refund_price=MoneyData.from_entity(line.refund_price),
            line_total=MoneyData.from_entity(line.line_total),
            is_reduced=line.is_reduced,
            refund_approved_by=line.refund_approved_by,
            refund_note=line.refund_note,
        )


class CustomerReturnData(CamelModel):
    id: UUID
    number: str
    status: DocumentStatus
    sales_invoice_id: UUID
    customer_id: UUID | None
    location_id: UUID
    reason: CustomerReturnReason
    # Som, and never a conversion of the subtotals below it (§4.7).
    debt_relief: MoneyData | None
    note: str | None
    created_by: UUID
    created_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    lines: list[CustomerReturnLineData]
    subtotals: list[MoneyData]
    # The running count §6 wants after every beep, so the operator never has
    # to count the list themselves.
    line_count: int

    @classmethod
    def from_entity(cls, document: CustomerReturn) -> CustomerReturnData:
        return cls(
            id=document.id,
            number=document.number,
            status=document.status,
            sales_invoice_id=document.sales_invoice_id,
            customer_id=document.customer_id,
            location_id=document.location_id,
            reason=document.reason,
            debt_relief=MoneyData.from_entity(document.debt_relief),
            note=document.note,
            created_by=document.created_by,
            created_at=document.created_at,
            confirmed_at=document.confirmed_at,
            cancelled_at=document.cancelled_at,
            cancellation_reason=document.cancellation_reason,
            lines=[CustomerReturnLineData.from_entity(line) for line in document.lines],
            subtotals=MoneyData.from_entity(document.subtotals()),
            line_count=len(document.lines),
        )
