"""Set or cut one handset's asking price — FR-2.15, FR-2.16, §4.5b.

Used stock that does not move gets cut, then cut again. That is the core
discipline of the trade, and it is why this is a command in its own right
rather than a field on a general "edit unit" endpoint: the act has its own
permission (§2.1), its own constraints, and its own append-only record.

Repricing writes **no** ``FinancialTransaction`` and changes no inventory
value, even below cost (FR-2.17) — see ``DeviceUnitRepricer``.
"""

from uuid import UUID

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.models import DeviceUnitData
from application.ports import DeviceUnitRepository, TenantUnitOfWork
from application.services import DeviceUnitLoader, DeviceUnitRepricer, SalePriceParser
from domain.permissions import Permission


class RepriceDeviceUnitCommandPayload(CamelModel):
    # A string or a whole number, never a JSON float — see
    # application/services/sale_price.py. Required: a price cannot be
    # un-set (§4.5b), so there is no ``None`` to accept here.
    asking_price: str | int
    reason: str | None = None


class RepriceDeviceUnitCommand(
    RepriceDeviceUnitCommandPayload, Command[ResultWithData[DeviceUnitData]]
):
    # A URL path segment, filled in by the router — never sent by the client.
    device_unit_id: UUID


class RepriceDeviceUnitHandler(
    IRequestHandler[ResultWithData[DeviceUnitData], RepriceDeviceUnitCommand]
):
    def __init__(
        self,
        units: DeviceUnitRepository,
        loader: DeviceUnitLoader,
        repricer: DeviceUnitRepricer,
        sale_price: SalePriceParser,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._units = units
        self._loader = loader
        self._repricer = repricer
        self._sale_price = sale_price
        self._uow = uow
        self._current = current

    async def handle(
        self, request: RepriceDeviceUnitCommand
    ) -> ResultWithData[DeviceUnitData]:
        unit, product = await self._loader.load(request.device_unit_id)

        # The currency is the product's, never the caller's: a unit cannot
        # be denominated differently from its catalog row (§4.5 rule 3).
        price = self._sale_price.parse(request.asking_price, product.currency)
        assert price is not None  # the field is required, so parse cannot return None

        await self._repricer.set_price(unit, price, request.reason)
        await self._units.update(unit)
        await self._uow.commit()

        return ResultWithData[DeviceUnitData].succeed_with_data(
            DeviceUnitData.from_entity(
                unit, product, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
