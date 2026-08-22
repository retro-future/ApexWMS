"""Reports read from what the documents already wrote (PRD §5.9).

Everything here is a read. A report never corrects the thing it reports
on: a wrong invoice is cancelled and re-entered (§4.4), not edited from a
table that noticed it.

Most of it sits behind ``Permission.Reporting.View`` — Manager and Owner.
The debtor list takes ``CustomerAccount.ViewAll`` instead, because §2.1
grades the two questions differently: a Seller may look up what the
customer in front of them owes, while the whole book is a business-health
figure.
"""

from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query

from application.core import PagedResult
from application.dtos import CurrentUser
from application.models import DebtorData, PriceDeviationData
from application.queries.list_debtors import ListDebtorsHandler, ListDebtorsQuery
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


@router.get("/debtors")
async def list_debtors(
    query: Annotated[ListDebtorsQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListDebtorsHandler],
) -> PagedResult[DebtorData]:
    """FR-11.10: every customer with a balance above zero, oldest debt
    first. No buckets and no overdue flag — store credit has no due
    date."""
    require(current, Permission.CUSTOMER_ACCOUNT_VIEW_ALL)
    return await handler.handle(query)
