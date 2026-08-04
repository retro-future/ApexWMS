"""Read one handset — PRD §8, FR-1.7, FR-7.2."""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import CurrentUser
from application.models import DeviceUnitData
from application.services import DeviceUnitLoader
from domain.permissions import Permission


class GetDeviceUnitQuery(Query[ResultWithData[DeviceUnitData]]):
    device_unit_id: UUID


class GetDeviceUnitHandler(IRequestHandler[ResultWithData[DeviceUnitData], GetDeviceUnitQuery]):
    def __init__(self, loader: DeviceUnitLoader, current: CurrentUser) -> None:
        self._loader = loader
        self._current = current

    async def handle(self, request: GetDeviceUnitQuery) -> ResultWithData[DeviceUnitData]:
        unit, product = await self._loader.load(request.device_unit_id)
        return ResultWithData[DeviceUnitData].succeed_with_data(
            DeviceUnitData.from_entity(
                unit,
                product,
                show_cost=Permission.COST_VIEW in self._current.permissions,
            )
        )
