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

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.models import WriteOffData
from application.ports import Clock, TenantUnitOfWork, WriteOffRepository
from application.services import DocumentLoader, LedgerPoster
from domain.enums import DocumentType


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
        write_offs: WriteOffRepository,
        loader: DocumentLoader,
        poster: LedgerPoster,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._write_offs = write_offs
        self._loader = loader
        self._poster = poster
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CancelWriteOffCommand
    ) -> ResultWithData[WriteOffData]:
        document = await self._loader.load_write_off(request.write_off_id)

        document.cancel(self._clock.now(), self._current.user_id, request.reason)
        await self._poster.reverse(DocumentType.WRITE_OFF, document.id)
        await self._write_offs.update(document)
        await self._uow.commit()

        return ResultWithData[WriteOffData].succeed_with_data(
            WriteOffData.from_entity(document)
        )
