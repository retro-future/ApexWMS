"""Edit or deactivate a supplier. Contact details are nullable, so they
are cleared only when the caller explicitly sends ``null``."""

from uuid import UUID

from pydantic import EmailStr, Field

from application.core import Command, IRequestHandler, ResultWithData
from application.errors import DuplicateNameError, NotFoundError
from application.ports import SupplierRepository, TenantUnitOfWork
from application.queries.get_supplier import SupplierData


class UpdateSupplierCommand(Command[ResultWithData[SupplierData]]):
    name: str | None = None
    contact_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    is_active: bool | None = None
    supplier_id: UUID | None = Field(default=None, exclude=True)


class UpdateSupplierHandler(
    IRequestHandler[ResultWithData[SupplierData], UpdateSupplierCommand]
):
    def __init__(self, suppliers: SupplierRepository, uow: TenantUnitOfWork) -> None:
        self._suppliers = suppliers
        self._uow = uow

    async def handle(self, request: UpdateSupplierCommand) -> ResultWithData[SupplierData]:
        assert request.supplier_id is not None
        supplier = await self._suppliers.get(request.supplier_id)
        if supplier is None:
            raise NotFoundError("no such supplier in this store")

        sent = request.model_fields_set
        if request.name is not None:
            name = request.name.strip()
            owner = await self._suppliers.get_by_name(name)
            if owner is not None and owner.id != supplier.id:
                raise DuplicateNameError(f"a supplier called {name!r} already exists")
            supplier.name = name
        if request.is_active is not None:
            supplier.is_active = request.is_active
        if "contact_name" in sent:
            supplier.contact_name = request.contact_name
        if "phone" in sent:
            supplier.phone = request.phone
        if "email" in sent:
            supplier.email = request.email

        await self._suppliers.update(supplier)
        await self._uow.commit()
        return ResultWithData[SupplierData].succeed_with_data(
            SupplierData.from_supplier(supplier)
        )
