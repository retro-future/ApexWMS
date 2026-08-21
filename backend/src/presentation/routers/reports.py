"""Reports read from what the documents already wrote (PRD §5.9).

Everything here is behind ``Permission.Reporting.View`` — Manager and Owner
— and everything here is a read. A report never corrects the thing it
reports on: a wrong invoice is cancelled and re-entered (§4.4), not edited
from a table that noticed it.
"""

from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query

from application.core import PagedResult
from application.dtos import CurrentUser
from application.models import PriceDeviationData
from application.queries.list_price_deviations import (
    ListPriceDeviationsHandler,
    ListPriceDeviationsQuery,
)
from domain.permissions import Permission
from presentation.security import bearer_scheme, require

router = APIRouter(
    prefix="/reports",
    tags=["reporting"],
    route_class=DishkaRoute,
    dependencies=[Depends(bearer_scheme)],
)


@router.get("/price-deviations")
async def list_price_deviations(
    query: Annotated[ListPriceDeviationsQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListPriceDeviationsHandler],
) -> PagedResult[PriceDeviationData]:
    """FR-9.7: what was charged against what the system resolved, and who
    approved the difference."""
    require(current, Permission.REPORTING_VIEW)
    return await handler.handle(query)
