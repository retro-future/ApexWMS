"""Read one supplier.

No currency field anywhere on a supplier: currency belongs to the product
(PRD §4.5 rule 3), so the same supplier can invoice in both.
"""

from uuid import UUID

from application.core import CamelModel, IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.ports import SupplierRepository
from domain.entities import Supplier


class SupplierData(CamelModel):
    id: UUID
    name: str
    contact_name: str | None
    phone: str | None
    email: str | None
    is_active: bool

    @classmethod
    def from_supplier(cls, supplier: Supplier) -> SupplierData:
        return cls(
            id=supplier.id,
            name=supplier.name,
            contact_name=supplier.contact_name,
            phone=supplier.phone,
            email=supplier.email,
            is_active=supplier.is_active,
        )


class GetSupplierQuery(Query[ResultWithData[SupplierData]]):
    supplier_id: UUID


class GetSupplierHandler(IRequestHandler[ResultWithData[SupplierData], GetSupplierQuery]):
    def __init__(self, suppliers: SupplierRepository) -> None:
        self._suppliers = suppliers

    async def handle(self, request: GetSupplierQuery) -> ResultWithData[SupplierData]:
        supplier = await self._suppliers.get(request.supplier_id)
        if supplier is None:
            raise NotFoundError("no such supplier in this store")
        return ResultWithData[SupplierData].succeed_with_data(
            SupplierData.from_supplier(supplier)
        )
