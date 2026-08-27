"""FR-9.2: everything that ever happened to one handset, in order.

*"A customer returns a phone claiming they bought it here"* (§1.1) is the
question this answers, and it is the milestone's demo: bought, priced, cut
twice, sold below asking, with the name of whoever approved that.

PRD §8 lists this as ``/devices/{imei}/history``. The route is on
``/device-units/{id}`` instead, beside the price history it extends, since
that is the shape every unit route in this codebase already has — and
``GET /scan/lookup`` is what turns a scanned IMEI into the id.
"""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import CurrentUser, UnitTrace
from application.models import DeviceTraceData
from application.services import DeviceUnitLoader, UnitTraceAssembler
from domain.permissions import Permission


class GetDeviceTraceQuery(Query[ResultWithData[DeviceTraceData]]):
    device_unit_id: UUID


class GetDeviceTraceHandler(
    IRequestHandler[ResultWithData[DeviceTraceData], GetDeviceTraceQuery]
):
    def __init__(
        self,
        units: DeviceUnitLoader,
        trace: UnitTraceAssembler,
        current: CurrentUser,
    ) -> None:
        self._units = units
        self._trace = trace
        self._current = current

    async def handle(
        self, request: GetDeviceTraceQuery
    ) -> ResultWithData[DeviceTraceData]:
        unit, product = await self._units.load(request.device_unit_id)
        events = await self._trace.events(request.device_unit_id)
        return ResultWithData[DeviceTraceData].succeed_with_data(
            DeviceTraceData.from_entity(
                UnitTrace(unit=unit, product=product, events=events),
                show_cost=Permission.COST_VIEW in self._current.permissions,
            )
        )
