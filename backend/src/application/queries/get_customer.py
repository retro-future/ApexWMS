"""Read one customer."""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import CustomerData
from application.ports import CustomerRepository


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
            CustomerData.from_entity(customer)
        )
