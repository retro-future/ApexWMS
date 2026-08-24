"""One Write-Off, with the lines scanned onto it so far."""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.models import WriteOffData
from application.services import DocumentLoader


class GetWriteOffQuery(Query[ResultWithData[WriteOffData]]):
    write_off_id: UUID


class GetWriteOffHandler(IRequestHandler[ResultWithData[WriteOffData], GetWriteOffQuery]):
    def __init__(self, loader: DocumentLoader) -> None:
        self._loader = loader

    async def handle(self, request: GetWriteOffQuery) -> ResultWithData[WriteOffData]:
        document = await self._loader.load_write_off(request.write_off_id)
        return ResultWithData[WriteOffData].succeed_with_data(
            WriteOffData.from_entity(document)
        )
