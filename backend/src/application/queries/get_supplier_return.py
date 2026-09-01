"""One Supplier Return, with the lines scanned onto it so far."""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import SupplierReturnData
from application.specs import SupplierReturnById
from domain.entities import SupplierReturn
from infrastructure.persistence.tenant.models import SupplierReturnModel


class GetSupplierReturnQuery(Query[ResultWithData[SupplierReturnData]]):
    supplier_return_id: UUID


class GetSupplierReturnHandler(
    IRequestHandler[ResultWithData[SupplierReturnData], GetSupplierReturnQuery]
):
    def __init__(
        self, returns: TenantDbRepository[SupplierReturn, SupplierReturnModel]
    ) -> None:
        self._returns = returns

    async def handle(
        self, request: GetSupplierReturnQuery
    ) -> ResultWithData[SupplierReturnData]:
        document = await self._returns.find_one(
            SupplierReturnById(request.supplier_return_id)
        )
        if document is None:
            raise NotFoundError(
                f"supplier return {request.supplier_return_id} does not exist in this store",
                key="not_found",
                subject_key="supplier_return",
            )
        return ResultWithData[SupplierReturnData].succeed_with_data(
            SupplierReturnData.from_entity(document)
        )
