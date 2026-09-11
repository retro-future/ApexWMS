"""Every rate the store has quoted, newest first (W9 B1).

The history is the point of the table: what the counter was told to charge
last Tuesday is how a sale from last Tuesday gets read back.
"""

from application.common.repository import TenantAppendOnlyRepository
from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import ExchangeRateData
from application.ports import Clock
from application.services import PeriodResolver
from application.specs import RateHistory
from domain.entities import ExchangeRate
from domain.enums import RateKind
from infrastructure.persistence.tenant.models import ExchangeRateModel


class ListExchangeRatesQuery(PagedQuery[PagedResult[ExchangeRateData]]):
    kind: RateKind = RateKind.SALE


class ListExchangeRatesHandler(
    IRequestHandler[PagedResult[ExchangeRateData], ListExchangeRatesQuery]
):
    def __init__(
        self,
        rates: TenantAppendOnlyRepository[ExchangeRate, ExchangeRateModel],
        periods: PeriodResolver,
        clock: Clock,
    ) -> None:
        self._rates = rates
        self._periods = periods
        self._clock = clock

    async def handle(
        self, request: ListExchangeRatesQuery
    ) -> PagedResult[ExchangeRateData]:
        today = await self._periods.today(self._clock.now())
        spec = RateHistory(request.kind)
        total = await self._rates.count(spec)
        quoted = await self._rates.find(spec.page(request.page, request.page_size))
        return PagedResult[ExchangeRateData].succeed_with_data(
            data=[ExchangeRateData.from_entity(rate, today) for rate in quoted],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
