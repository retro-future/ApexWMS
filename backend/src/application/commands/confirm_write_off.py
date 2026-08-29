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

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import WriteOffData
from application.ports import Clock, TenantUnitOfWork
from application.services import RemovalPoster
from application.specs import WriteOffForWrite
from domain.entities import WriteOff
from infrastructure.persistence.tenant.models import WriteOffModel


class ConfirmWriteOffCommand(Command[ResultWithData[WriteOffData]]):
    # No body: this action needs nothing beyond the write-off in the URL.
    write_off_id: UUID


class ConfirmWriteOffHandler(
    IRequestHandler[ResultWithData[WriteOffData], ConfirmWriteOffCommand]
):
    def __init__(
        self,
        write_offs: TenantDbRepository[WriteOff, WriteOffModel],
        poster: RemovalPoster,
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
        self, request: ConfirmWriteOffCommand
    ) -> ResultWithData[WriteOffData]:
        spec = WriteOffForWrite(request.write_off_id)
        document = await self._write_offs.find_one(spec)
        if document is None:
            raise NotFoundError(
                f"write-off {request.write_off_id} does not exist in this store"
            )

        document.confirm(self._clock.now(), self._current.user_id)
        await self._poster.write_off(document)
        await self._write_offs.update(document, spec)
        await self._uow.commit()

        return ResultWithData[WriteOffData].succeed_with_data(
            WriteOffData.from_entity(document)
        )
