"""Taking a handset back off an open write-off (FR-3.12).

Keyed by IMEI, because that is what the operator has in their hand. Draft
only: a confirmed write-off has already booked the loss, and it is
cancelled and re-entered rather than edited (§4.4).
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, Result
from application.errors import NotFoundError
from application.ports import TenantUnitOfWork
from application.specs import DeviceUnitByImei, WriteOffForWrite
from domain.entities import DeviceUnit, WriteOff
from domain.value_objects import IMEI
from infrastructure.persistence.tenant.models import DeviceUnitModel, WriteOffModel


class UnscanWriteOffLineCommand(Command[Result]):
    # No body: both values name what to remove and come straight off the URL.
    write_off_id: UUID
    imei: str


class UnscanWriteOffLineHandler(IRequestHandler[Result, UnscanWriteOffLineCommand]):
    def __init__(
        self,
        write_offs: TenantDbRepository[WriteOff, WriteOffModel],
        units: TenantDbRepository[DeviceUnit, DeviceUnitModel],
        uow: TenantUnitOfWork,
    ) -> None:
        self._write_offs = write_offs
        self._units = units
        self._uow = uow

    async def handle(self, request: UnscanWriteOffLineCommand) -> Result:
        spec = WriteOffForWrite(request.write_off_id)
        document = await self._write_offs.find_one(spec)
        if document is None:
            raise NotFoundError(
                f"write-off {request.write_off_id} does not exist in this store"
            )
        document.assert_editable()

        wanted = IMEI.parse(request.imei)
        unit = await self._units.find_one(DeviceUnitByImei(str(wanted)))
        line = None if unit is None else document.line_for_unit(unit.id)
        if line is None:
            raise NotFoundError(f"{document.number} has no scan of IMEI {wanted}")

        document.lines.remove(line)
        await self._write_offs.update(document, spec)
        await self._uow.commit()
        return Result.succeed(f"{wanted} removed from {document.number}")
