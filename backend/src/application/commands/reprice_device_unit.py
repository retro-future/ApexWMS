"""Set or cut one handset's asking price — FR-2.15, FR-2.16, §4.5b.

Used stock that does not move gets cut, then cut again. That is the core
discipline of the trade, and it is why this is a command in its own right
rather than a field on a general "edit unit" endpoint: the act has its own
permission (§2.1), its own constraints, and its own append-only record.

Repricing writes **no** ``FinancialTransaction`` and changes no inventory
value, even below cost (FR-2.17) — see ``DeviceUnitRepricer``.
"""

from uuid import UUID

from pydantic import Field

from application.core import Command, IRequestHandler, ResultWithData
from application.dtos import CurrentUser
from application.ports import (
    DeviceUnitRepository,
    ProductRepository,
    TenantUnitOfWork,
)
from application.queries.get_device_unit import DeviceUnitData, load_unit_with_product
from application.services import DeviceUnitRepricer, SalePriceParser
from domain.permissions import Permission


class RepriceDeviceUnitCommand(Command[ResultWithData[DeviceUnitData]]):
    # A string or a whole number, never a JSON float — see
    # application/services/sale_price.py. Required: a price cannot be
    # un-set (§4.5b), so there is no ``None`` to accept here.
    asking_price: str | int
    reason: str | None = None
    # A URL path segment, merged in by the router.
    device_unit_id: UUID | None = Field(default=None, exclude=True)


class RepriceDeviceUnitHandler(
    IRequestHandler[ResultWithData[DeviceUnitData], RepriceDeviceUnitCommand]
):
    def __init__(
        self,
        units: DeviceUnitRepository,
        products: ProductRepository,
        repricer: DeviceUnitRepricer,
        sale_price: SalePriceParser,
        uow: TenantUnitOfWork,
        current: CurrentUser,
    ) -> None:
        self._units = units
        self._products = products
        self._repricer = repricer
        self._sale_price = sale_price
        self._uow = uow
        self._current = current

    async def handle(
        self, request: RepriceDeviceUnitCommand
    ) -> ResultWithData[DeviceUnitData]:
        assert request.device_unit_id is not None
        unit, product = await load_unit_with_product(
            self._units, self._products, request.device_unit_id
        )

        # The currency is the product's, never the caller's: a unit cannot
        # be denominated differently from its catalog row (§4.5 rule 3).
        price = self._sale_price.parse(request.asking_price, product.currency)
        assert price is not None  # the field is required, so parse cannot return None

        await self._repricer.set_price(unit, price, request.reason)
        await self._units.update(unit)
        await self._uow.commit()

        return ResultWithData[DeviceUnitData].succeed_with_data(
            DeviceUnitData.from_unit(
                unit, product, show_cost=Permission.COST_VIEW in self._current.permissions
            )
        )
