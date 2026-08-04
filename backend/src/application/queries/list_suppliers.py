"""Who this store buys from."""

from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import SupplierData
from application.ports import SupplierRepository


class ListSuppliersQuery(PagedQuery[PagedResult[SupplierData]]):
    search: str | None = None
    is_active: bool | None = None


class ListSuppliersHandler(IRequestHandler[PagedResult[SupplierData], ListSuppliersQuery]):
    def __init__(self, suppliers: SupplierRepository) -> None:
        self._suppliers = suppliers

    async def handle(self, request: ListSuppliersQuery) -> PagedResult[SupplierData]:
        suppliers, total = await self._suppliers.list_page(
            page=request.page,
            page_size=request.page_size,
            search=request.search,
            is_active=request.is_active,
        )
        return PagedResult[SupplierData].succeed_with_data(
            data=[SupplierData.from_entity(s) for s in suppliers],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
