"""What has been written off, and why.

Filterable by ``reason`` (FR-6.5), which is what turns *"how much did theft
cost us this quarter"* into a query. That question is the reason the reason
is a closed set rather than a note.
"""

from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import WriteOffData
from application.ports import WriteOffRepository
from domain.enums import DocumentStatus, WriteOffReason


class ListWriteOffsQuery(PagedQuery[PagedResult[WriteOffData]]):
    search: str | None = None
    status: DocumentStatus | None = None
    location_id: UUID | None = None
    reason: WriteOffReason | None = None


class ListWriteOffsHandler(IRequestHandler[PagedResult[WriteOffData], ListWriteOffsQuery]):
    def __init__(self, write_offs: WriteOffRepository) -> None:
        self._write_offs = write_offs

    async def handle(self, request: ListWriteOffsQuery) -> PagedResult[WriteOffData]:
        documents, total = await self._write_offs.list_page(
            page=request.page,
            page_size=request.page_size,
            search=request.search,
            status=request.status,
            location_id=request.location_id,
            reason=request.reason,
        )
        return PagedResult[WriteOffData].succeed_with_data(
            data=[WriteOffData.from_entity(d) for d in documents],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
