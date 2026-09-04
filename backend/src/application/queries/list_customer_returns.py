"""What customers have brought back, and what is still being scanned.

Filterable by ``reason``, which is the point of FR-4.9's closed set:
*"how much of this month's stock came back defective?"* is a query rather
than a trawl through free-text notes.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import CustomerReturnData
from application.specs import CustomerReturnBrowse
from domain.entities import CustomerReturn
from domain.enums import CustomerReturnReason, DocumentStatus
from infrastructure.persistence.tenant.models import CustomerReturnModel


class ListCustomerReturnsQuery(PagedQuery[PagedResult[CustomerReturnData]]):
    search: str | None = None
    status: DocumentStatus | None = None
    customer_id: UUID | None = None
    location_id: UUID | None = None
    reason: CustomerReturnReason | None = None


class ListCustomerReturnsHandler(
    IRequestHandler[PagedResult[CustomerReturnData], ListCustomerReturnsQuery]
):
    def __init__(
        self, returns: TenantDbRepository[CustomerReturn, CustomerReturnModel]
    ) -> None:
        self._returns = returns

    async def handle(
        self, request: ListCustomerReturnsQuery
    ) -> PagedResult[CustomerReturnData]:
        spec = CustomerReturnBrowse(
            search=request.search,
            status=request.status,
            customer_id=request.customer_id,
            location_id=request.location_id,
            reason=request.reason,
        )
        total = await self._returns.count(spec)
        documents = await self._returns.find(spec.page(request.page, request.page_size))
        return PagedResult[CustomerReturnData].succeed_with_data(
            data=[CustomerReturnData.from_entity(d) for d in documents],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
