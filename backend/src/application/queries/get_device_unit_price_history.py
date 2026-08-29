"""Every price one handset has ever been offered at — §4.5b, FR-9.2.

*"We paid $300, asked $420, cut it twice, sold at $360"* is a question the
owner asks of a specific handset months later, and it is answerable only
because each of those cuts was a row rather than an overwrite.

The payload is the catalog log's (``PriceChangeData``): the two logs have
the same shape on purpose, so a client that can render one renders both.
"""

from uuid import UUID

from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.errors import NotFoundError
from application.models import PriceChangeData
from application.specs import DeviceUnitById, PriceChangesForUnit
from domain.entities import DeviceUnit, DeviceUnitPriceChange
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    DeviceUnitPriceChangeModel,
)


class GetDeviceUnitPriceHistoryQuery(Query[ResultWithData[list[PriceChangeData]]]):
    device_unit_id: UUID


class GetDeviceUnitPriceHistoryHandler(
    IRequestHandler[ResultWithData[list[PriceChangeData]], GetDeviceUnitPriceHistoryQuery]
):
    def __init__(
        self,
        units: TenantDbRepository[DeviceUnit, DeviceUnitModel],
        changes: TenantAppendOnlyRepository[
            DeviceUnitPriceChange, DeviceUnitPriceChangeModel
        ],
    ) -> None:
        self._units = units
        self._changes = changes

    async def handle(
        self, request: GetDeviceUnitPriceHistoryQuery
    ) -> ResultWithData[list[PriceChangeData]]:
        # An unpriced handset and an unknown one are different answers, and
        # only the lookup can tell them apart.
        if not await self._units.exists(DeviceUnitById(request.device_unit_id)):
            raise NotFoundError("no such device unit in this store")

        changes = await self._changes.find(PriceChangesForUnit(request.device_unit_id))
        return ResultWithData[list[PriceChangeData]].succeed_with_data(
            [PriceChangeData.from_entity(change) for change in changes]
        )
