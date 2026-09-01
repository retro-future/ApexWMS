"""FR-10.9: the month-end close as a file, on the store's letterhead.

Rendered on demand and never stored. The ledgers are immutable and no
figure is ever converted (FR-10.10), so a past month's file is the same
bytes every time it is asked for — which is only true because the renderer
pins the PDF's creation date to the period's end rather than the clock.
"""

from uuid import UUID

from pydantic import Field

from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import RenderedDocument
from application.localization.locale import Locale
from application.ports import MonthEndReportRenderer, TenantSettingsRepository
from application.services import MonthEndReporter


class GetMonthEndReportPdfQuery(Query[ResultWithData[RenderedDocument]]):
    year: int = Field(ge=2000, le=2999)
    month: int = Field(ge=1, le=12)
    location_id: UUID | None = None


class GetMonthEndReportPdfHandler(
    IRequestHandler[ResultWithData[RenderedDocument], GetMonthEndReportPdfQuery]
):
    def __init__(
        self,
        reporter: MonthEndReporter,
        settings: TenantSettingsRepository,
        renderer: MonthEndReportRenderer,
        locale: Locale,
    ) -> None:
        self._reporter = reporter
        self._settings = settings
        self._renderer = renderer
        self._locale = locale

    async def handle(
        self, request: GetMonthEndReportPdfQuery
    ) -> ResultWithData[RenderedDocument]:
        report = await self._reporter.report(
            request.year, request.month, request.location_id
        )
        letterhead = await self._settings.get_letterhead()
        return ResultWithData[RenderedDocument].succeed_with_data(
            RenderedDocument(
                filename=f"month-end-{report.period.year}-{report.period.month:02d}.pdf",
                content_type="application/pdf",
                content=self._renderer.render(report, letterhead, self._locale),
            )
        )
