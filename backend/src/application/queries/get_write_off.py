"""One Write-Off, with the lines scanned onto it so far."""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import WriteOffData
from application.specs import WriteOffById
from domain.entities import WriteOff
from infrastructure.persistence.tenant.models import WriteOffModel


class GetWriteOffQuery(Query[ResultWithData[WriteOffData]]):
    write_off_id: UUID


class GetWriteOffHandler(IRequestHandler[ResultWithData[WriteOffData], GetWriteOffQuery]):
    def __init__(self, write_offs: TenantDbRepository[WriteOff, WriteOffModel]) -> None:
        self._write_offs = write_offs

    async def handle(self, request: GetWriteOffQuery) -> ResultWithData[WriteOffData]:
        document = await self._write_offs.find_one(WriteOffById(request.write_off_id))
        if document is None:
            raise NotFoundError(
                f"write-off {request.write_off_id} does not exist in this store",
                key="not_found",
                subject_key="write_off",
            )
        return ResultWithData[WriteOffData].succeed_with_data(
            WriteOffData.from_entity(document)
        )
