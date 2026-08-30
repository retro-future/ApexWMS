"""What the shelves were worth at one instant — FR-10.5, FR-10.6.

Read from the two ledgers rather than from ``device_units.status`` and
``stock_levels``: the month-end report asks about a moment that has passed,
and a projection only ever answers about now. ``LedgerReconciler`` keeps
reading the projections, because catching one that has drifted is a
different question from valuing a closed month.

Accessories go through ``CostPoolReader`` with the same cutoff, so this
report and the FR-10.7 audit cannot disagree about what an average cost was
(§4.6).
"""

from datetime import datetime
from uuid import UUID

from application.dtos import LocationInventoryValue
from application.ports import StockMovementQueries
from application.services.cost_pools import CostPoolReader
from domain.value_objects import CurrencyTotals


class InventoryValuer:
    def __init__(self, movements: StockMovementQueries, pools: CostPoolReader) -> None:
        self._movements = movements
        self._pools = pools

    async def by_location(
        self, as_of: datetime, location_id: UUID | None = None
    ) -> list[LocationInventoryValue]:
        """FR-10.6: where the value physically sits, per currency."""
        quantities: dict[UUID, int] = {}
        names: dict[UUID, str | None] = {}
        values: dict[UUID, CurrencyTotals] = {}

        for row in await self._movements.serialized_value_at(as_of, location_id):
            names.setdefault(row.location_id, row.location_name)
            quantities[row.location_id] = quantities.get(row.location_id, 0) + row.quantity
            values[row.location_id] = values.get(
                row.location_id, CurrencyTotals.empty()
            ).add(row.amount)

        for product_id, place in await self._movements.moved_pairs(as_of):
            if location_id is not None and place != location_id:
                continue
            pool = await self._pools.pool_for(product_id, place, as_of)
            if pool is None or pool.value.is_zero:
                continue
            names.setdefault(place, None)
            quantities[place] = quantities.get(place, 0) + pool.quantity
            values[place] = values.get(place, CurrencyTotals.empty()).add(pool.value)

        return [
            LocationInventoryValue(
                location_id=place,
                location_name=names[place],
                quantity=quantities.get(place, 0),
                value=values.get(place, CurrencyTotals.empty()),
            )
            for place in sorted(names, key=lambda one: (names[one] or "", str(one)))
        ]

    async def total(
        self, as_of: datetime, location_id: UUID | None = None
    ) -> CurrencyTotals:
        totals = CurrencyTotals.empty()
        for entry in await self.by_location(as_of, location_id):
            totals = totals.merge(entry.value)
        return totals
