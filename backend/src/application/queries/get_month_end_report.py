"""FR-10.4: how the store did in one month, at one location or across all.

Not paged and not filterable beyond the period and the location. A month
is the unit here — half a month's purchases against a whole month's COGS
is not a smaller report, it is a wrong one.
"""

from uuid import UUID

from pydantic import Field

from application.core import IRequestHandler, Query, ResultWithData
from application.models import MonthEndReportData
from application.services import MonthEndReporter


class GetMonthEndReportQuery(Query[ResultWithData[MonthEndReportData]]):
    year: int = Field(ge=2000, le=2999)
    month: int = Field(ge=1, le=12)
    location_id: UUID | None = None


class GetMonthEndReportHandler(
    IRequestHandler[ResultWithData[MonthEndReportData], GetMonthEndReportQuery]
):
    def __init__(self, reporter: MonthEndReporter) -> None:
        self._reporter = reporter

    async def handle(
        self, request: GetMonthEndReportQuery
    ) -> ResultWithData[MonthEndReportData]:
        report = await self._reporter.report(
            request.year, request.month, request.location_id
        )
        return ResultWithData[MonthEndReportData].succeed_with_data(
            MonthEndReportData.from_entity(report)
        )
