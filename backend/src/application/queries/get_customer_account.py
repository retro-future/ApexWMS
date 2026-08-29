"""FR-11.9: what this customer owes, and what they were sold on credit.

Nothing here is read from a stored balance, because there is no stored
balance to read: the figure is ``Σ (debt − payments)`` over their open
invoices, rebuilt on every request (§4.7). A customer financed by a credit
company correctly reads zero — the company already paid the store in full.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import CustomerAccountData
from application.ports import Clock, SalesInvoiceQueries
from domain.entities import Customer
from infrastructure.persistence.tenant.models import CustomerModel


class GetCustomerAccountQuery(Query[ResultWithData[CustomerAccountData]]):
    customer_id: UUID


class GetCustomerAccountHandler(
    IRequestHandler[ResultWithData[CustomerAccountData], GetCustomerAccountQuery]
):
    def __init__(
        self,
        customers: TenantDbRepository[Customer, CustomerModel],
        invoices: SalesInvoiceQueries,
        clock: Clock,
    ) -> None:
        self._customers = customers
        self._invoices = invoices
        self._clock = clock

    async def handle(
        self, request: GetCustomerAccountQuery
    ) -> ResultWithData[CustomerAccountData]:
        customer = await self._customers.get(request.customer_id)
        if customer is None:
            raise NotFoundError("no such customer in this store")

        history = await self._invoices.credit_history_for(customer.id)
        return ResultWithData[CustomerAccountData].succeed_with_data(
            CustomerAccountData.from_entity(customer, history, self._clock.now())
        )
