"""Reports read from what the documents already wrote (PRD §5.9).

Everything here is a read. A report never corrects the thing it reports
on: a wrong invoice is cancelled and re-entered (§4.4), not edited from a
table that noticed it.

Three permissions, because §2.1 grades three questions. Most of this sits
behind ``Permission.Reporting.View`` — *what did we move*. The financial
ledger takes ``FinancialLedger.View`` — *what did we earn*. The debtor list
takes ``CustomerAccount.ViewAll`` — *what is the whole book owed*, as
against the single customer's balance a Seller may look up. All three land
on Manager and Owner today; the catalog keeps them apart so a future
custom role can hold one without the others.

Cost figures inside a report are narrower still: FR-1.7 omits them from the
payload without ``Cost.View`` rather than leaving a screen to hide them. The
month-end close is the exception that needs no such trimming: it is money
end to end, so it takes ``FinancialLedger.View`` and nothing in it is
optional.
"""

from typing import Annotated

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query, Response

from application.core import PagedResult, ResultWithData
from application.dtos import CurrentUser
from application.models import (
    AgeingRowData,
    BelowCostRowData,
    DebtorData,
    DeviceInventoryRowData,
    FinancialLedgerRowData,
    MonthEndReportData,
    MovementRowData,
    NeedsPricingRowData,
    PriceDeviationData,
    SalesSummaryData,
    StockOnHandData,
)
from application.queries.get_month_end_report import (
    GetMonthEndReportHandler,
    GetMonthEndReportQuery,
)
from application.queries.get_month_end_report_pdf import (
    GetMonthEndReportPdfHandler,
    GetMonthEndReportPdfQuery,
)
from application.queries.get_sales_summary import (
    GetSalesSummaryHandler,
    GetSalesSummaryQuery,
)
from application.queries.get_stock_on_hand import (
    GetStockOnHandHandler,
    GetStockOnHandQuery,
)
from application.queries.list_ageing import ListAgeingHandler, ListAgeingQuery
from application.queries.list_below_cost import (
    ListBelowCostHandler,
    ListBelowCostQuery,
)
from application.queries.list_debtors import ListDebtorsHandler, ListDebtorsQuery
from application.queries.list_device_inventory import (
    ListDeviceInventoryHandler,
    ListDeviceInventoryQuery,
)
from application.queries.list_financial_ledger import (
    ListFinancialLedgerHandler,
    ListFinancialLedgerQuery,
)
from application.queries.list_movements import (
    ListMovementsHandler,
    ListMovementsQuery,
)
from application.queries.list_needs_pricing import (
    ListNeedsPricingHandler,
    ListNeedsPricingQuery,
)
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


@router.get("/needs-pricing")
async def list_needs_pricing(
    query: Annotated[ListNeedsPricingQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListNeedsPricingHandler],
) -> PagedResult[NeedsPricingRowData]:
    """FR-9.6: in-stock handsets that resolve to no price, oldest first.

    Manager and Owner, because they are the only ones who can act on it:
    pricing is theirs (§2.1), and a Seller who found the list could not fix
    a single row on it."""
    require(current, Permission.REPORTING_VIEW)
    return await handler.handle(query)


@router.get("/below-cost")
async def list_below_cost(
    query: Annotated[ListBelowCostQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListBelowCostHandler],
) -> PagedResult[BelowCostRowData]:
    """FR-2.19 backwards: active accessories whose weighted-average cost has
    reached their catalog price, so every further sale books a loss until an
    Owner or Manager reprices them. A worklist, not a block — selling below
    cost can be deliberate."""
    require(current, Permission.REPORTING_VIEW)
    return await handler.handle(query)


@router.get("/ageing")
async def list_ageing(
    query: Annotated[ListAgeingQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListAgeingHandler],
) -> PagedResult[AgeingRowData]:
    """FR-9.4: handsets in stock longer than ``days``, with what they cost,
    what they are asking, and how many times they have been cut."""
    require(current, Permission.REPORTING_VIEW)
    return await handler.handle(query)


@router.get("/stock-on-hand", response_model_exclude_none=True)
async def get_stock_on_hand(
    query: Annotated[GetStockOnHandQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetStockOnHandHandler],
) -> PagedResult[StockOnHandData]:
    """FR-9.1: what is on the shelves, by location, product or brand, with
    its cost value per currency — never one merged figure."""
    require(current, Permission.REPORTING_VIEW)
    return await handler.handle(query)


@router.get("/device-units", response_model_exclude_none=True)
async def list_device_inventory(
    query: Annotated[ListDeviceInventoryQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListDeviceInventoryHandler],
) -> PagedResult[DeviceInventoryRowData]:
    """FR-9.1 at the unit level: every handset by IMEI, filterable by product,
    location, status and condition. Cost and margin are omitted from the
    payload without ``Cost.View``."""
    require(current, Permission.REPORTING_VIEW)
    return await handler.handle(query)


@router.get("/movements")
async def list_movements(
    query: Annotated[ListMovementsQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListMovementsHandler],
) -> PagedResult[MovementRowData]:
    """FR-9.5: the raw stock ledger. Nothing is excluded — a reversal sits
    beside the movement it reverses, because both happened."""
    require(current, Permission.REPORTING_VIEW)
    return await handler.handle(query)


@router.get("/financial-ledger")
async def list_financial_ledger(
    query: Annotated[ListFinancialLedgerQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[ListFinancialLedgerHandler],
) -> PagedResult[FinancialLedgerRowData]:
    """FR-10.3: the raw money ledger, mirroring the movement log. Each row
    carries its own currency; the report carries no total."""
    require(current, Permission.FINANCIAL_LEDGER_VIEW)
    return await handler.handle(query)


@router.get("/sales-summary")
async def get_sales_summary(
    query: Annotated[GetSalesSummaryQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetSalesSummaryHandler],
) -> ResultWithData[SalesSummaryData]:
    """FR-9.3: units sold, revenue, cost of goods and margin per location.

    Not paged: the store total is only meaningful with every location in
    hand, and a total of one page is the kind of figure that gets
    believed."""
    require(current, Permission.REPORTING_VIEW)
    return await handler.handle(query)


@router.get("/month-end")
async def get_month_end_report(
    query: Annotated[GetMonthEndReportQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetMonthEndReportHandler],
) -> ResultWithData[MonthEndReportData]:
    """FR-10.4: one month, one location or all of them, every figure per
    currency.

    A failed reconciliation (FR-10.7, FR-10.7b) comes back in the payload
    beside the numbers rather than as an error: the mismatch is surfaced,
    and the owner still gets the month.
    """
    require(current, Permission.FINANCIAL_LEDGER_VIEW)
    return await handler.handle(query)


@router.get("/month-end/pdf", response_class=Response)
async def get_month_end_report_pdf(
    query: Annotated[GetMonthEndReportPdfQuery, Query()],
    current: FromDishka[CurrentUser],
    handler: FromDishka[GetMonthEndReportPdfHandler],
) -> Response:
    """FR-10.9: the same close, on the store's letterhead."""
    require(current, Permission.FINANCIAL_LEDGER_VIEW)
    result = await handler.handle(query)
    assert result.data is not None
    rendered = result.data
    return Response(
        content=rendered.content,
        media_type=rendered.content_type,
        headers={"Content-Disposition": f'inline; filename="{rendered.filename}"'},
    )
