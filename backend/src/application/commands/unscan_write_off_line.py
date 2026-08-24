"""Taking a handset back off an open write-off (FR-3.12).

Keyed by IMEI, because that is what the operator has in their hand. Draft
only: a confirmed write-off has already booked the loss, and it is
cancelled and re-entered rather than edited (§4.4).
"""

from uuid import UUID

from application.core import Command, IRequestHandler, Result
from application.errors import NotFoundError
from application.ports import DeviceUnitRepository, TenantUnitOfWork, WriteOffRepository
from application.services import DocumentLoader
from domain.value_objects import IMEI


class UnscanWriteOffLineCommand(Command[Result]):
    # No body: both values name what to remove and come straight off the URL.
    write_off_id: UUID
    imei: str


class UnscanWriteOffLineHandler(IRequestHandler[Result, UnscanWriteOffLineCommand]):
    def __init__(
        self,
        write_offs: WriteOffRepository,
        units: DeviceUnitRepository,
        loader: DocumentLoader,
        uow: TenantUnitOfWork,
    ) -> None:
        self._write_offs = write_offs
        self._units = units
        self._loader = loader
        self._uow = uow

    async def handle(self, request: UnscanWriteOffLineCommand) -> Result:
        document = await self._loader.load_write_off(request.write_off_id)
        document.assert_editable()

        wanted = IMEI.parse(request.imei)
        unit = await self._units.get_by_imei(str(wanted))
        line = None if unit is None else document.line_for_unit(unit.id)
        if line is None:
            raise NotFoundError(f"{document.number} has no scan of IMEI {wanted}")

        document.lines.remove(line)
        await self._write_offs.remove_line(line.id)
        await self._uow.commit()
        return Result.succeed(f"{wanted} removed from {document.number}")
