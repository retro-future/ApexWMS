"""FR-2.2: a Seller creates a customer at the counter.

Names are *not* unique — two people are called Aziz Karimov, and refusing
the second one at the till would be absurd.
"""

from uuid import uuid4

from application.core import Command, IRequestHandler, ResultWithData
from application.ports import Clock, CustomerRepository, TenantUnitOfWork
from application.queries.get_customer import CustomerData
from domain.entities import Customer


class CreateCustomerCommand(Command[ResultWithData[CustomerData]]):
    full_name: str
    phone: str | None = None


class CreateCustomerHandler(
    IRequestHandler[ResultWithData[CustomerData], CreateCustomerCommand]
):
    def __init__(
        self, customers: CustomerRepository, clock: Clock, uow: TenantUnitOfWork
    ) -> None:
        self._customers = customers
        self._clock = clock
        self._uow = uow

    async def handle(self, request: CreateCustomerCommand) -> ResultWithData[CustomerData]:
        customer = Customer(
            id=uuid4(),
            full_name=request.full_name.strip(),
            phone=request.phone,
            is_active=True,
            created_at=self._clock.now(),
        )
        await self._customers.add(customer)
        await self._uow.commit()
        return ResultWithData[CustomerData].succeed_with_data(
            CustomerData.from_customer(customer)
        )
