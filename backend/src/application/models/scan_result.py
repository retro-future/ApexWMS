"""What one beep of the scanner returns — PRD §6.

The scanning contract puts the whole burden on this response: the operator
is holding the phone, and the answer has to be accept-or-reject *now*, not
when a fifty-unit receipt is submitted. A rejection is an error status with
the reason; an acceptance is this, carrying the running count so the
screen can say "7 of 10" without a second request.
"""

from __future__ import annotations

from uuid import UUID

from application.core import CamelModel
from application.models.received_unit import ReceivedUnitData
from domain.entities import GoodsReceiptLine, ReceivedUnit


class ScanResultData(CamelModel):
    line_id: UUID
    scanned_count: int
    expected_count: int
    unit: ReceivedUnitData

    @classmethod
    def from_entity(
        cls, unit: ReceivedUnit, line: GoodsReceiptLine, *, show_cost: bool
    ) -> ScanResultData:
        return cls(
            line_id=line.id,
            scanned_count=len(line.units),
            expected_count=line.quantity,
            unit=ReceivedUnitData.from_entity(unit, line, show_cost=show_cost),
        )
