"""Read one supplier."""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import SupplierData
from application.specs import SupplierById
from domain.entities import Supplier
from infrastructure.persistence.tenant.models import SupplierModel


class GetSupplierQuery(Query[ResultWithData[SupplierData]]):
    supplier_id: UUID


class GetSupplierHandler(IRequestHandler[ResultWithData[SupplierData], GetSupplierQuery]):
    def __init__(self, suppliers: TenantDbRepository[Supplier, SupplierModel]) -> None:
        self._suppliers = suppliers

    async def handle(self, request: GetSupplierQuery) -> ResultWithData[SupplierData]:
        supplier = await self._suppliers.find_one(SupplierById(request.supplier_id))
        if supplier is None:
            raise NotFoundError("no such supplier in this store")
        return ResultWithData[SupplierData].succeed_with_data(
            SupplierData.from_entity(supplier)
        )
