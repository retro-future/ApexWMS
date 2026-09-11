"""Both rates in force, and whether either is out of date (W9 B1)."""

from application.common.repository import TenantAppendOnlyRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.models import CurrentRatesData
from application.ports import Clock
from application.services import PeriodResolver
from application.specs import LatestRateFor
from domain.entities import ExchangeRate
from domain.enums import RateKind
from infrastructure.persistence.tenant.models import ExchangeRateModel


class GetCurrentRatesQuery(Query[ResultWithData[CurrentRatesData]]):
    pass


class GetCurrentRatesHandler(
    IRequestHandler[ResultWithData[CurrentRatesData], GetCurrentRatesQuery]
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
        self, request: GetCurrentRatesQuery
    ) -> ResultWithData[CurrentRatesData]:
        today = await self._periods.today(self._clock.now())
        return ResultWithData[CurrentRatesData].succeed_with_data(
            CurrentRatesData.from_entity(
                await self._rates.find_one(LatestRateFor(RateKind.SALE)),
                await self._rates.find_one(LatestRateFor(RateKind.BUYBACK)),
                today,
            )
        )
