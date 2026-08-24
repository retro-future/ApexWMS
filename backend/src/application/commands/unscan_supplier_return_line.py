"""Taking a handset back off an open supplier return (FR-3.12).

Keyed by IMEI rather than by line id, because that is what the operator
has: they are holding the phone they just scanned by mistake, and the line
id is on a screen they would have to read back.

Draft only. A confirmed return has already written both ledgers, and it is
cancelled and re-entered rather than edited (§4.4).
"""

from uuid import UUID

from application.core import Command, IRequestHandler, Result
from application.errors import NotFoundError
from application.ports import DeviceUnitRepository, SupplierReturnRepository, TenantUnitOfWork
from application.services import DocumentLoader
from domain.value_objects import IMEI


class UnscanSupplierReturnLineCommand(Command[Result]):
    # No body: both values name what to remove and come straight off the
    # URL, built by the router with no request model in between.
    supplier_return_id: UUID
    imei: str


class UnscanSupplierReturnLineHandler(
    IRequestHandler[Result, UnscanSupplierReturnLineCommand]
):
    def __init__(
        self,
        returns: SupplierReturnRepository,
        units: DeviceUnitRepository,
        loader: DocumentLoader,
        uow: TenantUnitOfWork,
    ) -> None:
        self._returns = returns
        self._units = units
        self._loader = loader
        self._uow = uow

    async def handle(self, request: UnscanSupplierReturnLineCommand) -> Result:
        document = await self._loader.load_return(request.supplier_return_id)
        document.assert_editable()

        wanted = IMEI.parse(request.imei)
        unit = await self._units.get_by_imei(str(wanted))
        line = None if unit is None else document.line_for_unit(unit.id)
        if line is None:
            raise NotFoundError(f"{document.number} has no scan of IMEI {wanted}")

        document.lines.remove(line)
        await self._returns.remove_line(line.id)
        await self._uow.commit()
        return Result.succeed(f"{wanted} removed from {document.number}")
