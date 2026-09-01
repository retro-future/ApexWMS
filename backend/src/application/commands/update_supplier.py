"""Edit or deactivate a supplier. Contact details are nullable, so they
are cleared only when the caller explicitly sends ``null``."""

from uuid import UUID

from pydantic import EmailStr, Field

from application.common.repository import TenantDbRepository
from application.common.specification import Specification
from application.core import Command, IRequestHandler, ResultWithData
from application.errors import DuplicateNameError, NotFoundError
from application.models import SupplierData
from application.ports import TenantUnitOfWork
from application.specs import SupplierForWrite
from domain.entities import Supplier
from infrastructure.persistence.tenant.models import SupplierModel


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
    def __init__(
        self,
        suppliers: TenantDbRepository[Supplier, SupplierModel],
        uow: TenantUnitOfWork,
    ) -> None:
        self._suppliers = suppliers
        self._uow = uow

    async def handle(self, request: UpdateSupplierCommand) -> ResultWithData[SupplierData]:
        assert request.supplier_id is not None
        supplier = await self._suppliers.find_one(SupplierForWrite(request.supplier_id))
        if supplier is None:
            raise NotFoundError(
                "no such supplier in this store",
                key="not_found",
                subject_key="supplier",
            )

        sent = request.model_fields_set
        if request.name is not None:
            name = request.name.strip()
            taken = Specification(SupplierModel).where(
                SupplierModel.name == name, SupplierModel.id != supplier.id
            )
            if await self._suppliers.exists(taken):
                raise DuplicateNameError(
                    f"a supplier called {name!r} already exists",
                    subject_key="supplier",
                    name=name,
                )
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
            SupplierData.from_entity(supplier)
        )
