"""One Customer Return, with the lines scanned onto it so far."""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import CustomerReturnData
from application.specs import CustomerReturnById
from domain.entities import CustomerReturn
from infrastructure.persistence.tenant.models import CustomerReturnModel


class GetCustomerReturnQuery(Query[ResultWithData[CustomerReturnData]]):
    customer_return_id: UUID


class GetCustomerReturnHandler(
    IRequestHandler[ResultWithData[CustomerReturnData], GetCustomerReturnQuery]
):
    def __init__(
        self, returns: TenantDbRepository[CustomerReturn, CustomerReturnModel]
    ) -> None:
        self._returns = returns

    async def handle(
        self, request: GetCustomerReturnQuery
    ) -> ResultWithData[CustomerReturnData]:
        document = await self._returns.find_one(
            CustomerReturnById(request.customer_return_id)
        )
        if document is None:
            raise NotFoundError(
                f"customer return {request.customer_return_id} does not exist in "
                "this store",
                key="not_found",
                subject_key="customer_return",
            )
        return ResultWithData[CustomerReturnData].succeed_with_data(
            CustomerReturnData.from_entity(document)
        )
