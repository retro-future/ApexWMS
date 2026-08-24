"""Response payload for a Stock Count — PRD §5.6, §8.

This payload **is** FR-6.3's discrepancy report. The three lists are not
computed by a separate close endpoint and handed back once: every row
carries its own ``outcome``, so the same response answers "what does this
count say" before the close, after it, and after the confirm. The counts
alongside them are what the operator reads at a glance while still standing
at the shelf.

``acquisitionCost`` sits behind ``Permission.Cost.View`` (FR-1.7), like
every other cost figure. It is the one money field here, and it appears on
exactly the rows that need it: a handset the store has no row for, which
confirming will create (FR-6.4b). Everything else on this payload is a fact
about goods, which is why a Storekeeper — who runs counts but may not see
costs (§2.1) — still reads the whole discrepancy report.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from application.core import CamelModel
from domain.entities import StockCount, StockCountLine, StockCountUnit
from domain.enums import CountOutcome, DocumentStatus


class StockCountUnitData(CamelModel):
    id: UUID
    imei: str
    device_unit_id: UUID | None
    product_id: UUID | None
    expected: bool
    scanned: bool
    outcome: CountOutcome
    # True where confirming has to *create* the handset, which is the only
    # row a cost must be stated on (FR-6.4b).
    is_surprise: bool
    # --- Permission.Cost.View only (FR-1.7) ---
    acquisition_cost: Decimal | None = None
    acquisition_cost_minor: int | None = None

    @classmethod
    def from_entity(cls, unit: StockCountUnit, *, show_cost: bool) -> StockCountUnitData:
        data = cls(
            id=unit.id,
            imei=str(unit.imei),
            device_unit_id=unit.device_unit_id,
            product_id=unit.product_id,
            expected=unit.expected,
            scanned=unit.scanned,
            outcome=unit.outcome,
            is_surprise=unit.is_surprise,
        )
        if not show_cost or unit.acquisition_cost is None:
            return data
        return data.model_copy(
            update={
                "acquisition_cost": unit.acquisition_cost.as_major(),
                "acquisition_cost_minor": unit.acquisition_cost.amount_minor,
            }
        )


class StockCountLineData(CamelModel):
    id: UUID
    product_id: UUID
    expected_quantity: int
    # Null until somebody counts, which is not the same as counting zero.
    counted_quantity: int | None
    delta: int

    @classmethod
    def from_entity(cls, line: StockCountLine) -> StockCountLineData:
        return cls(
            id=line.id,
            product_id=line.product_id,
            expected_quantity=line.expected_quantity,
            counted_quantity=line.counted_quantity,
            delta=line.delta,
        )


class StockCountData(CamelModel):
    id: UUID
    number: str
    status: DocumentStatus
    location_id: UUID
    note: str | None
    created_by: UUID
    created_at: datetime
    # The fourth step the shared DocumentStatus has no value for (§4.4).
    closed_at: datetime | None
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    units: list[StockCountUnitData]
    lines: list[StockCountLineData]
    # FR-6.3's three lists, as figures the operator reads at a glance.
    matched_count: int
    missing_count: int
    unexpected_count: int

    @classmethod
    def from_entity(cls, count: StockCount, *, show_cost: bool) -> StockCountData:
        return cls(
            id=count.id,
            number=count.number,
            status=count.status,
            location_id=count.location_id,
            note=count.note,
            created_by=count.created_by,
            created_at=count.created_at,
            closed_at=count.closed_at,
            confirmed_at=count.confirmed_at,
            cancelled_at=count.cancelled_at,
            cancellation_reason=count.cancellation_reason,
            units=[
                StockCountUnitData.from_entity(unit, show_cost=show_cost)
                for unit in count.units
            ],
            lines=[StockCountLineData.from_entity(line) for line in count.lines],
            matched_count=len(count.matched()),
            missing_count=len(count.missing()),
            unexpected_count=len(count.unexpected()),
        )
