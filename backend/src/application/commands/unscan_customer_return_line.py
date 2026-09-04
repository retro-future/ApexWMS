"""Taking a handset back off an open customer return (FR-3.12).

Keyed by IMEI rather than by line id, because that is what the operator
has: they are holding the phone they just scanned by mistake, and the line
id is on a screen they would have to read back.

Draft only. A confirmed return has already written both ledgers and paid the
customer, and it is cancelled and re-entered rather than edited (§4.4).
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import Command, IRequestHandler, Result
from application.errors import NotFoundError
from application.ports import TenantUnitOfWork
from application.specs import CustomerReturnForWrite, DeviceUnitByImei
from domain.entities import CustomerReturn, DeviceUnit
from domain.value_objects import IMEI
from infrastructure.persistence.tenant.models import CustomerReturnModel, DeviceUnitModel


class UnscanCustomerReturnLineCommand(Command[Result]):
    # No body: both values name what to remove and come straight off the
    # URL, built by the router with no request model in between.
    customer_return_id: UUID
    imei: str


class UnscanCustomerReturnLineHandler(
    IRequestHandler[Result, UnscanCustomerReturnLineCommand]
):
    def __init__(
        self,
        returns: TenantDbRepository[CustomerReturn, CustomerReturnModel],
        units: TenantDbRepository[DeviceUnit, DeviceUnitModel],
        uow: TenantUnitOfWork,
    ) -> None:
        self._returns = returns
        self._units = units
        self._uow = uow

    async def handle(self, request: UnscanCustomerReturnLineCommand) -> Result:
        spec = CustomerReturnForWrite(request.customer_return_id)
        document = await self._returns.find_one(spec)
        if document is None:
            raise NotFoundError(
                f"customer return {request.customer_return_id} does not exist in "
                "this store",
                key="not_found",
                subject_key="customer_return",
            )
        document.assert_editable()

        wanted = IMEI.parse(request.imei)
        unit = await self._units.find_one(DeviceUnitByImei(str(wanted)))
        line = None if unit is None else document.line_for_unit(unit.id)
        if line is None:
            raise NotFoundError(
                f"{document.number} has no scan of IMEI {wanted}",
                key="not_found_scan",
                imei=str(wanted),
            )

        document.lines.remove(line)
        await self._returns.update(document, spec)
        await self._uow.commit()
        return Result.succeed(f"{wanted} removed from {document.number}")
