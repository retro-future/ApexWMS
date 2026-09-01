"""Cancelling a confirmed write-off (§4.4, FR-10.2).

**Compensation, never deletion**, as everywhere else. The handsets are
reprojected from their own timelines, which walks each one back from
``WRITTEN_OFF`` to ``IN_STOCK`` at the location it left from — the case
this exists for is a phone written off as lost and then found.

Their asking prices are untouched throughout: a write-off never repriced
anything, so a recovered handset comes back to the shelf asking exactly
what it asked before.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import WriteOffData
from application.ports import Clock, TenantUnitOfWork
from application.services import LedgerPoster
from application.specs import WriteOffForWrite
from domain.entities import WriteOff
from domain.enums import DocumentType
from infrastructure.persistence.tenant.models import WriteOffModel


class CancelWriteOffCommandPayload(CamelModel):
    reason: str | None = None


class CancelWriteOffCommand(
    CancelWriteOffCommandPayload, Command[ResultWithData[WriteOffData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    write_off_id: UUID


class CancelWriteOffHandler(
    IRequestHandler[ResultWithData[WriteOffData], CancelWriteOffCommand]
):
    def __init__(
        self,
        write_offs: TenantDbRepository[WriteOff, WriteOffModel],
        poster: LedgerPoster,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._write_offs = write_offs
        self._poster = poster
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CancelWriteOffCommand
    ) -> ResultWithData[WriteOffData]:
        spec = WriteOffForWrite(request.write_off_id)
        document = await self._write_offs.find_one(spec)
        if document is None:
            raise NotFoundError(
                f"write-off {request.write_off_id} does not exist in this store",
                key="not_found",
                subject_key="write_off",
            )

        document.cancel(self._clock.now(), self._current.user_id, request.reason)
        await self._poster.reverse(DocumentType.WRITE_OFF, document.id)
        await self._write_offs.update(document, spec)
        await self._uow.commit()

        return ResultWithData[WriteOffData].succeed_with_data(
            WriteOffData.from_entity(document)
        )
