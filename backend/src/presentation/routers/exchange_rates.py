"""The rate the store quotes: read by anyone, set by an Owner or a Manager."""

from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query

from application.commands.set_exchange_rate import (
    SetExchangeRateCommand,
    SetExchangeRateHandler,
)
from application.core import PagedResult, ResultWithData
from application.dtos import CurrentUser
from application.models import CurrentRatesData, ExchangeRateData
from application.queries.get_current_rates import (
    GetCurrentRatesHandler,
    GetCurrentRatesQuery,
)
from application.queries.list_exchange_rates import (
    ListExchangeRatesHandler,
    ListExchangeRatesQuery,
)
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/exchange-rates",
    tags=["exchange-rates"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.get("/current")
async def get_current(
    current: FromDishka[CurrentUser], handler: FromDishka[GetCurrentRatesHandler]
) -> ResultWithData[CurrentRatesData]:
    require(current, Permission.EXCHANGE_RATE_VIEW)
    return await handler.handle(GetCurrentRatesQuery())


@router.get("")
async def list_rates(
    query: Annotated[ListExchangeRatesQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListExchangeRatesHandler],
) -> PagedResult[ExchangeRateData]:
    require(current, Permission.EXCHANGE_RATE_VIEW)
    return await handler.handle(query)


@router.post("")
async def set_rate(
    body: SetExchangeRateCommand,
    current: FromDishka[CurrentUser],
    handler: FromDishka[SetExchangeRateHandler],
) -> ResultWithData[ExchangeRateData]:
    require(current, Permission.EXCHANGE_RATE_MANAGE)
    return await handler.handle(body)
