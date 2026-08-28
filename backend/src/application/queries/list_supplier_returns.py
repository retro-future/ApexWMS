"""What has gone back to suppliers, and what is still being scanned.

Filterable by ``reason``, which is the point of FR-5.1's closed set:
*"how much did this supplier send us defective?"* is a query rather than a
trawl through free-text notes.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import SupplierReturnData
from application.specs import SupplierReturnBrowse
from domain.entities import SupplierReturn
from domain.enums import DocumentStatus, SupplierReturnReason
from infrastructure.persistence.tenant.models import SupplierReturnModel


class ListSupplierReturnsQuery(PagedQuery[PagedResult[SupplierReturnData]]):
    search: str | None = None
    status: DocumentStatus | None = None
    supplier_id: UUID | None = None
    reason: SupplierReturnReason | None = None


class ListSupplierReturnsHandler(
    IRequestHandler[PagedResult[SupplierReturnData], ListSupplierReturnsQuery]
):
    def __init__(
        self, returns: TenantDbRepository[SupplierReturn, SupplierReturnModel]
    ) -> None:
        self._returns = returns

    async def handle(
        self, request: ListSupplierReturnsQuery
    ) -> PagedResult[SupplierReturnData]:
        spec = SupplierReturnBrowse(
            search=request.search,
            status=request.status,
            supplier_id=request.supplier_id,
            reason=request.reason,
        )
        total = await self._returns.count(spec)
        documents = await self._returns.find(
            spec.page(request.page, request.page_size)
        )
        return PagedResult[SupplierReturnData].succeed_with_data(
            data=[SupplierReturnData.from_entity(d) for d in documents],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
