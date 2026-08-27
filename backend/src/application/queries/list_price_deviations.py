"""FR-9.7: every confirmed line charged something other than the resolved price.

The report exists to make a pattern visible rather than to police a
transaction. A single discount is a negotiation; *"one manager, one
customer, over and over"* is something the owner needs to see, which is why
the approver and the customer are filters here rather than columns to scan
by eye.

It reports **both** directions. A handset sold above its asking price is
information too, so nothing here filters on the sign of the difference.
"""

from datetime import datetime
from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import PriceDeviationData
from application.ports import SalesReportRepository
from application.sorting import DeviationSort


class ListPriceDeviationsQuery(PagedQuery[PagedResult[PriceDeviationData]]):
    from_date: datetime | None = None
    to_date: datetime | None = None
    approved_by: UUID | None = None
    customer_id: UUID | None = None
    sort: DeviationSort = DeviationSort.CONFIRMED_AT


class ListPriceDeviationsHandler(
    IRequestHandler[PagedResult[PriceDeviationData], ListPriceDeviationsQuery]
):
    def __init__(self, sales: SalesReportRepository) -> None:
        self._sales = sales

    async def handle(
        self, request: ListPriceDeviationsQuery
    ) -> PagedResult[PriceDeviationData]:
        deviations, total = await self._sales.list_deviations(
            page=request.page,
            page_size=request.page_size,
            from_date=request.from_date,
            to_date=request.to_date,
            approved_by=request.approved_by,
            customer_id=request.customer_id,
            sort=request.sort,
        )
        return PagedResult[PriceDeviationData].succeed_with_data(
            data=[PriceDeviationData.from_entity(one) for one in deviations],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
