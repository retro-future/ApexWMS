"""What one beep of the scanner during a count returns — PRD §6, FR-6.2.

Its own file rather than a branch of ``StockCountData`` because a count
holds the **whole shelf**: an opening snapshot of a stockroom is hundreds
of rows, and re-serialising all of them after every trigger pull is exactly
what §6's 200ms budget rules out. The supplier return and write-off scans
return their whole document instead, because those are bounded by what one
person carries to the counter in one go.

**One of ``unit`` and ``line`` is set, never both** — §6's "one endpoint,
two possible answers" in a payload. A handset comes back as the count row
it marked, an accessory as the line whose tally it bumped, and the operator
never had to tell the server which kind of code they were pointing at.

The three counts ride along for the same reason ``lineCount`` does on the
other documents: the operator is holding a phone and must not have to look
away to know where the count stands.
"""

from __future__ import annotations

from application.core import CamelModel
from application.models.stock_count import StockCountLineData, StockCountUnitData
from domain.entities import StockCount, StockCountLine, StockCountUnit


class CountScanResultData(CamelModel):
    unit: StockCountUnitData | None = None
    line: StockCountLineData | None = None
    matched_count: int
    missing_count: int
    unexpected_count: int

    @classmethod
    def from_entity(
        cls,
        count: StockCount,
        found: StockCountUnit | StockCountLine,
        *,
        show_cost: bool,
    ) -> CountScanResultData:
        unit = (
            StockCountUnitData.from_entity(found, show_cost=show_cost)
            if isinstance(found, StockCountUnit)
            else None
        )
        line = (
            StockCountLineData.from_entity(found, show_cost=show_cost)
            if isinstance(found, StockCountLine)
            else None
        )
        return cls(
            unit=unit,
            line=line,
            matched_count=len(count.matched()),
            missing_count=len(count.missing()),
            unexpected_count=len(count.unexpected()),
        )
