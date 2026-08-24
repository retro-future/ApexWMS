"""What has gone back to suppliers, and what is still being scanned.

Filterable by ``reason``, which is the point of FR-5.1's closed set:
*"how much did this supplier send us defective?"* is a query rather than a
trawl through free-text notes.
"""

from uuid import UUID

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import SupplierReturnData
from application.ports import SupplierReturnRepository
from domain.enums import DocumentStatus, SupplierReturnReason


class ListSupplierReturnsQuery(PagedQuery[PagedResult[SupplierReturnData]]):
    search: str | None = None
    status: DocumentStatus | None = None
    supplier_id: UUID | None = None
    reason: SupplierReturnReason | None = None


class ListSupplierReturnsHandler(
    IRequestHandler[PagedResult[SupplierReturnData], ListSupplierReturnsQuery]
):
    def __init__(self, returns: SupplierReturnRepository) -> None:
        self._returns = returns

    async def handle(
        self, request: ListSupplierReturnsQuery
    ) -> PagedResult[SupplierReturnData]:
        documents, total = await self._returns.list_page(
            page=request.page,
            page_size=request.page_size,
            search=request.search,
            status=request.status,
            supplier_id=request.supplier_id,
            reason=request.reason,
        )
        return PagedResult[SupplierReturnData].succeed_with_data(
            data=[SupplierReturnData.from_entity(d) for d in documents],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
