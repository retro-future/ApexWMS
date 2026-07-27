"""Read one customer.

Deliberately anemic (PRD §4.2). What a customer *owes* is not here: it is
derived from their invoices and payments (§4.7, M5b), so there is no
balance field that could drift from the ledger.
"""

from uuid import UUID

from application.core import CamelModel, IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.ports import CustomerRepository
from domain.entities import Customer


class CustomerData(CamelModel):
    id: UUID
    full_name: str
    phone: str | None
    is_active: bool

    @classmethod
    def from_customer(cls, customer: Customer) -> CustomerData:
        return cls(
            id=customer.id,
            full_name=customer.full_name,
            phone=customer.phone,
            is_active=customer.is_active,
        )


class GetCustomerQuery(Query[ResultWithData[CustomerData]]):
    customer_id: UUID


class GetCustomerHandler(IRequestHandler[ResultWithData[CustomerData], GetCustomerQuery]):
    def __init__(self, customers: CustomerRepository) -> None:
        self._customers = customers

    async def handle(self, request: GetCustomerQuery) -> ResultWithData[CustomerData]:
        customer = await self._customers.get(request.customer_id)
        if customer is None:
            raise NotFoundError("no such customer in this store")
        return ResultWithData[CustomerData].succeed_with_data(
            CustomerData.from_customer(customer)
        )
