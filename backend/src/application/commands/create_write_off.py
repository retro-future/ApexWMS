"""FR-6.5: a Manager opens a write-off.

Header only — every line arrives by scan. The reason is mandatory and is
stated here rather than at confirm: what happened to the goods is known
before anyone starts picking them off the shelf, and a write-off that could
be confirmed without saying why would leave the loss report unable to tell
theft from breakage.
"""

from uuid import UUID, uuid4

from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.models import WriteOffData
from application.ports import (
    Clock,
    LocationRepository,
    TenantUnitOfWork,
    WriteOffRepository,
)
from application.services import DocumentNumberer
from domain.entities import WriteOff
from domain.enums import DocumentStatus, DocumentType, WriteOffReason


class CreateWriteOffCommand(Command[ResultWithData[WriteOffData]]):
    location_id: UUID
    reason: WriteOffReason
    note: str | None = None


class CreateWriteOffHandler(
    IRequestHandler[ResultWithData[WriteOffData], CreateWriteOffCommand]
):
    def __init__(
        self,
        write_offs: WriteOffRepository,
        locations: LocationRepository,
        numberer: DocumentNumberer,
        clock: Clock,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._write_offs = write_offs
        self._locations = locations
        self._numberer = numberer
        self._clock = clock
        self._uow = uow
        self._current = current

    async def handle(
        self, request: CreateWriteOffCommand
    ) -> ResultWithData[WriteOffData]:
        if await self._locations.get(request.location_id) is None:
            raise NotFoundError(
                f"location {request.location_id} does not exist in this store"
            )

        document = WriteOff(
            id=uuid4(),
            number=await self._numberer.next(DocumentType.WRITE_OFF),
            status=DocumentStatus.DRAFT,
            location_id=request.location_id,
            reason=request.reason,
            note=request.note,
            created_by=self._current.user_id,
            created_at=self._clock.now(),
        )
        await self._write_offs.add(document)
        await self._uow.commit()

        return ResultWithData[WriteOffData].succeed_with_data(
            WriteOffData.from_entity(document)
        )
