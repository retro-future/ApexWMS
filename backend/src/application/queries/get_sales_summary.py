"""FR-9.3: what selling earned, by location, over a date range.

Not paged. A store has a handful of locations, and the store total is only
meaningful with all of them in hand — a page of it would be a total of the
page, which is the kind of figure that gets believed.
"""

from datetime import datetime
from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import (
    LocationSales,
    SalesFigures,
    SalesSummary,
    SalesTotalsRow,
)
from application.models import SalesSummaryData
from application.ports import FinancialTransactionQueries, StockMovementQueries
from domain.enums import TransactionType
from domain.value_objects import CurrencyTotals


class GetSalesSummaryQuery(Query[ResultWithData[SalesSummaryData]]):
    from_date: datetime | None = None
    to_date: datetime | None = None
    location_id: UUID | None = None


class GetSalesSummaryHandler(
    IRequestHandler[ResultWithData[SalesSummaryData], GetSalesSummaryQuery]
):
    def __init__(
        self,
        transactions: FinancialTransactionQueries,
        movements: StockMovementQueries,
    ) -> None:
        self._transactions = transactions
        self._movements = movements

    async def handle(
        self, request: GetSalesSummaryQuery
    ) -> ResultWithData[SalesSummaryData]:
        rows = await self._transactions.sales_totals(
            from_date=request.from_date,
            to_date=request.to_date,
            location_id=request.location_id,
        )
        sold = await self._movements.units_sold(
            from_date=request.from_date,
            to_date=request.to_date,
            location_id=request.location_id,
        )
        locations = self._by_location(rows, sold)
        return ResultWithData[SalesSummaryData].succeed_with_data(
            SalesSummaryData.from_entity(
                SalesSummary(
                    from_date=request.from_date,
                    to_date=request.to_date,
                    locations=locations,
                    total=self._total(locations),
                )
            )
        )

    def _by_location(
        self, rows: list[SalesTotalsRow], sold: dict[UUID, int]
    ) -> list[LocationSales]:
        """Both sides are unioned rather than joined on the money side.

        A confirm writes goods and money in one transaction (FR-10.1), so
        the two agree — and if they ever do not, the odd one out should
        appear as a row with a hole in it rather than vanish.
        """
        names: dict[UUID | None, str | None] = {}
        buckets: dict[TransactionType, dict[UUID | None, CurrencyTotals]] = {
            TransactionType.SALE_REVENUE: {},
            TransactionType.COGS: {},
            TransactionType.SALES_RETURN_REFUND: {},
        }

        for row in rows:
            names.setdefault(row.location_id, row.location_name)
            into = buckets[row.txn_type]
            into[row.location_id] = into.get(
                row.location_id, CurrencyTotals.empty()
            ).add(row.amount)
        for location_id in sold:
            names.setdefault(location_id, None)

        def figure(txn_type: TransactionType, location_id: UUID | None) -> CurrencyTotals:
            return buckets[txn_type].get(location_id, CurrencyTotals.empty())

        return [
            LocationSales(
                location_id=location_id,
                location_name=names[location_id],
                figures=SalesFigures(
                    units_sold=sold.get(location_id, 0) if location_id else 0,
                    revenue=figure(TransactionType.SALE_REVENUE, location_id),
                    cost_of_goods=figure(TransactionType.COGS, location_id),
                    returns=figure(TransactionType.SALES_RETURN_REFUND, location_id),
                ),
            )
            for location_id in sorted(names, key=lambda one: (names[one] or "", str(one)))
        ]

    @staticmethod
    def _total(locations: list[LocationSales]) -> SalesFigures:
        revenue = CurrencyTotals.empty()
        cost = CurrencyTotals.empty()
        returns = CurrencyTotals.empty()
        units = 0
        for entry in locations:
            revenue = revenue.merge(entry.figures.revenue)
            cost = cost.merge(entry.figures.cost_of_goods)
            returns = returns.merge(entry.figures.returns)
            units += entry.figures.units_sold
        return SalesFigures(
            units_sold=units,
            revenue=revenue,
            cost_of_goods=cost,
            returns=returns,
        )
