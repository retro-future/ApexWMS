"""One group of the stock-on-hand report — FR-9.1, PRD §5.9.

``key`` is a string whatever the grouping is — a location or product id, or
the brand itself — because ``groupBy`` on the same row already says how to
read it, and one typed field per dimension would leave two of the three
null on every row.

``costValue`` is a list of per-currency subtotals rather than a number, and
is omitted entirely without ``Permission.Cost.View`` (FR-9.1, FR-1.7).
"""

from __future__ import annotations

from application.core import CamelModel
from application.dtos import StockGroupBy, StockOnHandGroup
from application.models.currency_subtotal import CurrencySubtotalData


class StockOnHandData(CamelModel):
    group_by: StockGroupBy
    key: str | None
    label: str
    quantity: int
    # Only set when grouping by product; None for location/brand rows.
    sku: str | None = None
    # --- Permission.Cost.View only (FR-9.1) ---
    cost_value: list[CurrencySubtotalData] | None = None

    @classmethod
    def from_entity(
        cls, group: StockOnHandGroup, *, show_cost: bool
    ) -> StockOnHandData:
        data = cls(
            group_by=group.group_by,
            key=None if group.key is None else str(group.key),
            label=group.label,
            quantity=group.quantity,
            sku=group.sku,
        )
        if not show_cost:
            return data
        return data.model_copy(
            update={
                "cost_value": CurrencySubtotalData.from_entity(
                    group.cost_value.as_dict()
                )
            }
        )
