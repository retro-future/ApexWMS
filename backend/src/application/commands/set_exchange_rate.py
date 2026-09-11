"""Quote a rate for a day (W9 B1).

Always a new row, never an update. Correcting this morning's figure at noon
leaves both, so a sale confirmed at 11:00 still reads what it was struck
against.

The rate arrives as a string for the reason prices do: a JSON float cannot
hold a decimal exactly, and this number multiplies money.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from application.common.repository import TenantAppendOnlyRepository
from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.models import ExchangeRateData
from application.ports import Clock, TenantUnitOfWork
from application.services import PeriodResolver
from domain.entities import ExchangeRate
from domain.enums import RateKind
from domain.errors import InvalidExchangeRateError
from infrastructure.persistence.tenant.models import ExchangeRateModel


class SetExchangeRateCommand(Command[ResultWithData[ExchangeRateData]]):
    kind: RateKind
    som_per_usd: str
    # Defaults to the store's own today. Present so a manager can enter a
    # rate for yesterday after the fact rather than backdating by hand.
    effective_on: date | None = None


class SetExchangeRateHandler(
    IRequestHandler[ResultWithData[ExchangeRateData], SetExchangeRateCommand]
):
    def __init__(
        self,
        rates: TenantAppendOnlyRepository[ExchangeRate, ExchangeRateModel],
        periods: PeriodResolver,
        clock: Clock,
        current: CurrentUser,
        uow: TenantUnitOfWork,
    ) -> None:
        self._rates = rates
        self._periods = periods
        self._clock = clock
        self._current = current
        self._uow = uow

    async def handle(
        self, request: SetExchangeRateCommand
    ) -> ResultWithData[ExchangeRateData]:
        now = self._clock.now()
        today = await self._periods.today(now)
        rate = ExchangeRate(
            kind=request.kind,
            effective_on=request.effective_on or today,
            som_per_usd=self._parse(request.som_per_usd),
            user_id=self._current.user_id,
            set_at=now,
        )
        await self._rates.add(rate)
        await self._uow.commit()
        return ResultWithData[ExchangeRateData].succeed_with_data(
            ExchangeRateData.from_entity(rate, today)
        )

    @staticmethod
    def _parse(raw: str) -> Decimal:
        try:
            return Decimal(raw.strip())
        except (InvalidOperation, ValueError) as exc:
            raise InvalidExchangeRateError(f"{raw!r} is not a number", rate=raw) from exc
