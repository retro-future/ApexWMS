"""The IMEI trace — FR-9.2, PRD §5.9.

The header reuses ``DeviceUnitData``, which already omits cost, margin and
``cashPaid`` without ``Permission.Cost.View`` (FR-1.7) and already renders
the som figure as a *string* so nothing can add it to anything (FR-3.4d).

The events carry prices, never costs, so none of them is behind a
permission: what a handset was asked for is what the counter needs to know.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.dtos import TraceEvent, TraceEventKind, UnitOrigin, UnitSale, UnitTrace
from application.models.device_unit import DeviceUnitData
from application.models.money import MoneyData
from domain.enums import AcquisitionSource, DocumentType


class TraceOriginData(CamelModel):
    acquisition_source: AcquisitionSource
    supplier_id: UUID | None
    supplier_name: str | None
    customer_id: UUID | None
    customer_name: str | None

    @classmethod
    def from_entity(cls, origin: UnitOrigin) -> TraceOriginData:
        return cls(
            acquisition_source=origin.acquisition_source,
            supplier_id=origin.supplier_id,
            supplier_name=origin.supplier_name,
            customer_id=origin.customer_id,
            customer_name=origin.customer_name,
        )


class TraceSaleData(CamelModel):
    invoice_id: UUID
    invoice_number: str
    customer_id: UUID | None
    customer_name: str | None
    resolved_price: MoneyData | None
    charged_price: MoneyData | None
    price_approved_by: UUID | None
    price_approved_by_name: str | None
    price_note: str | None

    @classmethod
    def from_entity(cls, sale: UnitSale) -> TraceSaleData:
        return cls(
            invoice_id=sale.invoice_id,
            invoice_number=sale.invoice_number,
            customer_id=sale.customer_id,
            customer_name=sale.customer_name,
            resolved_price=MoneyData.from_entity(sale.resolved_price),
            charged_price=MoneyData.from_entity(sale.charged_price),
            price_approved_by=sale.price_approved_by,
            price_approved_by_name=sale.price_approved_by_name,
            price_note=sale.price_note,
        )


class TraceEventData(CamelModel):
    kind: TraceEventKind
    occurred_at: datetime
    user_id: UUID
    user_name: str | None
    note: str | None
    document_type: DocumentType | None
    document_id: UUID | None
    document_number: str | None
    location_id: UUID | None
    location_name: str | None
    # PRICED only. Null ``oldPrice`` is the first pricing, not a cut.
    old_price: MoneyData | None
    new_price: MoneyData | None
    origin: TraceOriginData | None
    sale: TraceSaleData | None

    @classmethod
    def from_entity(cls, event: TraceEvent) -> TraceEventData:
        return cls(
            kind=event.kind,
            occurred_at=event.occurred_at,
            user_id=event.actor.user_id,
            user_name=event.actor.user_name,
            note=event.note,
            document_type=event.document_type,
            document_id=event.document_id,
            document_number=event.document_number,
            location_id=event.location_id,
            location_name=event.location_name,
            old_price=MoneyData.from_entity(event.old_price),
            new_price=MoneyData.from_entity(event.new_price),
            origin=TraceOriginData.from_entity(event.origin) if event.origin else None,
            sale=TraceSaleData.from_entity(event.sale) if event.sale else None,
        )


class DeviceTraceData(CamelModel):
    unit: DeviceUnitData
    events: list[TraceEventData]

    @classmethod
    def from_entity(cls, trace: UnitTrace, *, show_cost: bool) -> DeviceTraceData:
        return cls(
            unit=DeviceUnitData.from_entity(
                trace.unit, trace.product, show_cost=show_cost
            ),
            events=[TraceEventData.from_entity(event) for event in trace.events],
        )
