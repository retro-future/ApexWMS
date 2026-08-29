"""FR-11.10: who owes the store money, worst-first.

No buckets and no overdue column, because store credit has no due date
(§4.7) and inventing one here would be the schedule the owner said they do
not keep. What the list orders by instead is the age of each customer's
oldest open invoice, so a debt that has been sitting for a year rises to
the top on its own.
"""

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import DebtorData
from application.ports import Clock, SalesInvoiceQueries


class ListDebtorsQuery(PagedQuery[PagedResult[DebtorData]]):
    pass


class ListDebtorsHandler(IRequestHandler[PagedResult[DebtorData], ListDebtorsQuery]):
    def __init__(self, sales: SalesInvoiceQueries, clock: Clock) -> None:
        self._sales = sales
        self._clock = clock

    async def handle(self, request: ListDebtorsQuery) -> PagedResult[DebtorData]:
        debtors, total = await self._sales.list_debtors(
            page=request.page, page_size=request.page_size
        )
        now = self._clock.now()
        return PagedResult[DebtorData].succeed_with_data(
            data=[DebtorData.from_entity(debtor, now) for debtor in debtors],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
