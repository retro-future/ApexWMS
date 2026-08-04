"""Who this store sells to. Search matches name or phone — at the counter
a seller has the phone number, not the id."""

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import CustomerData
from application.ports import CustomerRepository


class ListCustomersQuery(PagedQuery[PagedResult[CustomerData]]):
    search: str | None = None
    is_active: bool | None = None


class ListCustomersHandler(IRequestHandler[PagedResult[CustomerData], ListCustomersQuery]):
    def __init__(self, customers: CustomerRepository) -> None:
        self._customers = customers

    async def handle(self, request: ListCustomersQuery) -> PagedResult[CustomerData]:
        customers, total = await self._customers.list_page(
            page=request.page,
            page_size=request.page_size,
            search=request.search,
            is_active=request.is_active,
        )
        return PagedResult[CustomerData].succeed_with_data(
            data=[CustomerData.from_entity(c) for c in customers],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
