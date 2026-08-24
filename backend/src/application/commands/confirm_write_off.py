"""FR-6.5: confirming a write-off, and the only writer of ``WRITE_OFF_LOSS``.

The same shape as ``ConfirmSupplierReturnHandler`` against the other
removal document: the aggregate decides whether it may be confirmed,
``RemovalPoster`` takes the goods off the shelf at their book value, and
this handler owns the transaction both ledgers are written inside.

A count shortage never reaches here. It books ``COUNT_ADJUSTMENT`` under
its own count (§4.6), even though the handset lands in the same
``WRITTEN_OFF`` status — so the loss report counts only losses somebody
could name a cause for.
"""

from uuid import UUID

from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.models import WriteOffData
from application.ports import Clock, TenantUnitOfWork, WriteOffRepository
from application.services import DocumentLoader, RemovalPoster


class ConfirmWriteOffCommand(Command[ResultWithData[WriteOffData]]):
    # No body: this action needs nothing beyond the write-off in the URL.
    write_off_id: UUID


class ConfirmWriteOffHandler(
    IRequestHandler[ResultWithData[WriteOffData], ConfirmWriteOffCommand]
):
    def __init__(
        self,
        write_offs: WriteOffRepository,
        loader: DocumentLoader,
        poster: RemovalPoster,
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
        self, request: ConfirmWriteOffCommand
    ) -> ResultWithData[WriteOffData]:
        document = await self._loader.load_write_off(request.write_off_id)

        document.confirm(self._clock.now(), self._current.user_id)
        await self._poster.write_off(document)
        await self._write_offs.update(document)
        await self._uow.commit()

        return ResultWithData[WriteOffData].succeed_with_data(
            WriteOffData.from_entity(document)
        )
