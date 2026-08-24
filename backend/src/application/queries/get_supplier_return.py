"""One Supplier Return, with the lines scanned onto it so far."""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.models import SupplierReturnData
from application.services import DocumentLoader


class GetSupplierReturnQuery(Query[ResultWithData[SupplierReturnData]]):
    supplier_return_id: UUID


class GetSupplierReturnHandler(
    IRequestHandler[ResultWithData[SupplierReturnData], GetSupplierReturnQuery]
):
    def __init__(self, loader: DocumentLoader) -> None:
        self._loader = loader

    async def handle(
        self, request: GetSupplierReturnQuery
    ) -> ResultWithData[SupplierReturnData]:
        document = await self._loader.load_return(request.supplier_return_id)
        return ResultWithData[SupplierReturnData].succeed_with_data(
            SupplierReturnData.from_entity(document)
        )
