"""Who this store sells to. Search matches name or phone — at the counter
a seller has the phone number, not the id."""

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import CustomerData
from application.specs import CustomerBrowse
from domain.entities import Customer
from infrastructure.persistence.tenant.models import CustomerModel


class ListCustomersQuery(PagedQuery[PagedResult[CustomerData]]):
    search: str | None = None
    is_active: bool | None = None


class ListCustomersHandler(IRequestHandler[PagedResult[CustomerData], ListCustomersQuery]):
    def __init__(self, customers: TenantDbRepository[Customer, CustomerModel]) -> None:
        self._customers = customers

    async def handle(self, request: ListCustomersQuery) -> PagedResult[CustomerData]:
        spec = CustomerBrowse(search=request.search, is_active=request.is_active)
        total = await self._customers.count(spec)
        customers = await self._customers.find(spec.page(request.page, request.page_size))
        return PagedResult[CustomerData].succeed_with_data(
            data=[CustomerData.from_entity(c) for c in customers],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
