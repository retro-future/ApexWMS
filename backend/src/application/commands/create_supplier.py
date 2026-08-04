"""FR-2.2: a Manager creates a supplier.

Names are unique within the store, so the supplier column on a purchase
order names one company unambiguously.
"""

from uuid import uuid4

from pydantic import EmailStr

from application.core import Command, IRequestHandler, ResultWithData
from application.errors import DuplicateNameError
from application.models import SupplierData
from application.ports import Clock, SupplierRepository, TenantUnitOfWork
from domain.entities import Supplier


class CreateSupplierCommand(Command[ResultWithData[SupplierData]]):
    name: str
    contact_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None


class CreateSupplierHandler(
    IRequestHandler[ResultWithData[SupplierData], CreateSupplierCommand]
):
    def __init__(
        self, suppliers: SupplierRepository, clock: Clock, uow: TenantUnitOfWork
    ) -> None:
        self._suppliers = suppliers
        self._clock = clock
        self._uow = uow

    async def handle(self, request: CreateSupplierCommand) -> ResultWithData[SupplierData]:
        name = request.name.strip()
        if await self._suppliers.get_by_name(name) is not None:
            raise DuplicateNameError(f"a supplier called {name!r} already exists")

        supplier = Supplier(
            id=uuid4(),
            name=name,
            contact_name=request.contact_name,
            phone=request.phone,
            email=request.email,
            is_active=True,
            created_at=self._clock.now(),
        )
        await self._suppliers.add(supplier)
        await self._uow.commit()
        return ResultWithData[SupplierData].succeed_with_data(
            SupplierData.from_entity(supplier)
        )
