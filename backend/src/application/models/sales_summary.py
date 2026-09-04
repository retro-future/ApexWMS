"""The sales summary — FR-9.3, PRD §5.9.

Every money figure is a list of per-currency subtotals, never a number, so
there is nowhere a USD total and a UZS total could be added together
(FR-2.11). ``costOfGoods`` and ``returns`` keep §4.6's sign and are
therefore **negative**: money left for the goods, money handed back on a
return. ``margin`` is their plain sum with ``revenue``, which is why no
sign is flipped anywhere in this report.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from application.core import CamelModel
from application.dtos import LocationSales, SalesFigures, SalesSummary
from application.models.currency_subtotal import CurrencySubtotalData


class SalesFiguresData(CamelModel):
    units_sold: int
    revenue: list[CurrencySubtotalData]
    cost_of_goods: list[CurrencySubtotalData]
    # Negative: money handed back on customer returns (FR-4.9).
    returns: list[CurrencySubtotalData]
    margin: list[CurrencySubtotalData]

    @classmethod
    def from_entity(cls, figures: SalesFigures) -> SalesFiguresData:
        return cls(
            units_sold=figures.units_sold,
            revenue=CurrencySubtotalData.from_entity(figures.revenue.as_dict()),
            cost_of_goods=CurrencySubtotalData.from_entity(
                figures.cost_of_goods.as_dict()
            ),
            returns=CurrencySubtotalData.from_entity(figures.returns.as_dict()),
            margin=CurrencySubtotalData.from_entity(figures.margin),
        )


class LocationSalesData(CamelModel):
    location_id: UUID | None
    location_name: str | None
    figures: SalesFiguresData

    @classmethod
    def from_entity(cls, entry: LocationSales) -> LocationSalesData:
        return cls(
            location_id=entry.location_id,
            location_name=entry.location_name,
            figures=SalesFiguresData.from_entity(entry.figures),
        )


class SalesSummaryData(CamelModel):
    from_date: datetime | None
    to_date: datetime | None
    locations: list[LocationSalesData]
    total: SalesFiguresData

    @classmethod
    def from_entity(cls, summary: SalesSummary) -> SalesSummaryData:
        return cls(
            from_date=summary.from_date,
            to_date=summary.to_date,
            locations=[
                LocationSalesData.from_entity(entry) for entry in summary.locations
            ],
            total=SalesFiguresData.from_entity(summary.total),
        )
