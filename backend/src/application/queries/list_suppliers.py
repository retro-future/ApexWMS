"""Who this store buys from."""

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, PagedQuery, PagedResult
from application.models import SupplierData
from application.specs import SupplierBrowse
from domain.entities import Supplier
from infrastructure.persistence.tenant.models import SupplierModel


class ListSuppliersQuery(PagedQuery[PagedResult[SupplierData]]):
    search: str | None = None
    is_active: bool | None = None


class ListSuppliersHandler(IRequestHandler[PagedResult[SupplierData], ListSuppliersQuery]):
    def __init__(self, suppliers: TenantDbRepository[Supplier, SupplierModel]) -> None:
        self._suppliers = suppliers

    async def handle(self, request: ListSuppliersQuery) -> PagedResult[SupplierData]:
        spec = SupplierBrowse(search=request.search, is_active=request.is_active)
        # Counted before page() narrows the same spec object.
        total = await self._suppliers.count(spec)
        suppliers = await self._suppliers.find(spec.page(request.page, request.page_size))
        return PagedResult[SupplierData].succeed_with_data(
            data=[SupplierData.from_entity(s) for s in suppliers],
            page_index=request.page,
            page_size=request.page_size,
            items_count=total,
        )
