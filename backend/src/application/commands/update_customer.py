"""Correct a customer's details, or deactivate them.

Never a delete: their invoices and, from M5b, their debt history point
here.
"""

from uuid import UUID

from pydantic import Field

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, ResultWithData
from application.errors import NotFoundError
from application.models import CustomerData
from application.ports import TenantUnitOfWork
from application.specs import CustomerForWrite
from domain.entities import Customer
from infrastructure.persistence.tenant.models import CustomerModel


class UpdateCustomerCommand(Command[ResultWithData[CustomerData]]):
    full_name: str | None = None
    phone: str | None = None
    is_active: bool | None = None
    customer_id: UUID | None = Field(default=None, exclude=True)


class UpdateCustomerHandler(
    IRequestHandler[ResultWithData[CustomerData], UpdateCustomerCommand]
):
    def __init__(
        self,
        customers: TenantDbRepository[Customer, CustomerModel],
        uow: TenantUnitOfWork,
    ) -> None:
        self._customers = customers
        self._uow = uow

    async def handle(self, request: UpdateCustomerCommand) -> ResultWithData[CustomerData]:
        assert request.customer_id is not None
        customer = await self._customers.find_one(CustomerForWrite(request.customer_id))
        if customer is None:
            raise NotFoundError("no such customer in this store")

        if request.full_name is not None:
            customer.full_name = request.full_name.strip()
        if request.is_active is not None:
            customer.is_active = request.is_active
        if "phone" in request.model_fields_set:
            customer.phone = request.phone

        await self._customers.update(customer)
        await self._uow.commit()
        return ResultWithData[CustomerData].succeed_with_data(
            CustomerData.from_entity(customer)
        )
