"""Change a handset's condition — FR-2.18.

``condition`` is **a pricing input, not a description**, which is why this
is Owner/Manager and not something a Storekeeper edits alongside a serial
number. It is the single field that decides whether a unit may inherit its
model's catalog price (FR-2.14).

The consequence is stated rather than discovered: flipping a ``NEW`` unit
that holds no asking price to ``USED`` makes it **unsellable** — it stops
resolving to a price, rather than silently continuing to quote the new
price of the model. That is the intended behaviour, and the unit then
surfaces on the needs-pricing worklist (FR-9.6).
"""

from uuid import UUID

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.models import DeviceUnitData
from application.ports import DeviceUnitRepository, TenantUnitOfWork
from application.services import DeviceUnitLoader
from domain.enums import DeviceCondition
from domain.errors import UnitNotRepriceableError
from domain.permissions import Permission


class ChangeDeviceUnitConditionCommandPayload(CamelModel):
    condition: DeviceCondition


class ChangeDeviceUnitConditionCommand(
    ChangeDeviceUnitConditionCommandPayload, Command[ResultWithData[DeviceUnitData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    device_unit_id: UUID


class ChangeDeviceUnitConditionHandler(
    IRequestHandler[ResultWithData[DeviceUnitData], ChangeDeviceUnitConditionCommand]
):
    def __init__(
        self,
        units: DeviceUnitRepository,
        loader: DeviceUnitLoader,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._units = units
        self._loader = loader
        self._uow = uow
        self._current = current

    async def handle(
        self, request: ChangeDeviceUnitConditionCommand
    ) -> ResultWithData[DeviceUnitData]:
        unit, product = await self._loader.load(request.device_unit_id)

        # Same constraint as repricing, for the same reason: condition
        # governs price, and re-grading a handset that has already been
        # sold could only make its history disagree with what it fetched.
        if not unit.status.is_on_hand:
            raise UnitNotRepriceableError(
                f"IMEI {unit.imei} is {unit.status.value} — its condition is settled"
            )

        unit.condition = request.condition
        await self._units.update(unit)
        await self._uow.commit()

        return ResultWithData[DeviceUnitData].succeed_with_data(
            DeviceUnitData.from_entity(
                unit, product, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
