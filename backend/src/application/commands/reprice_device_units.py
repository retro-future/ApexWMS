"""Reprice many handsets in one call — FR-2.21, PRD §8.

This route exists because the ageing report (FR-9.4) and the needs-pricing
worklist (FR-9.6) both hand the owner a *list* of handsets to act on, and
pricing them one HTTP call at a time is the interaction those reports were
built to avoid.

It is **not** a different kind of write. Each unit's new price is stated
explicitly — there is no "cut everything by 10%", because a percentage
across handsets in different conditions is exactly the automated valuation
§1.3 rejects, merely applied to several at once. One
``device_unit_price_change`` per unit, under the same permission and the
same ``IN_STOCK``/``RESERVED`` constraint as the single-unit route.

**Atomic**: one ineligible unit rejects the whole call with nothing
written. The owner marking down eight units off a report needs to know
that what they saw is what happened, and a partial success that silently
priced six of them is worse than a refusal.
"""

from uuid import UUID

from pydantic import Field

from application.common.repository import TenantDbRepository
from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.errors import NotFoundError
from application.ports import (
    TenantUnitOfWork,
)
from application.services import DeviceUnitRepricer, SalePriceParser
from application.specs import DeviceUnitsByIds
from domain.entities import DeviceUnit, Product
from domain.value_objects import Money
from infrastructure.persistence.tenant.models import DeviceUnitModel, ProductModel


class UnitPrice(CamelModel):
    device_unit_id: UUID
    asking_price: str | int


class RepriceDeviceUnitsCommand(Command[ResultWithData[int]]):
    prices: list[UnitPrice] = Field(min_length=1)
    # One shared reason for the batch: these are one decision applied to
    # several handsets ("Ramadan clearance"), not several decisions.
    reason: str | None = None


class RepriceDeviceUnitsHandler(
    IRequestHandler[ResultWithData[int], RepriceDeviceUnitsCommand]
):
    def __init__(
        self,
        units: TenantDbRepository[DeviceUnit, DeviceUnitModel],
        products: TenantDbRepository[Product, ProductModel],
        repricer: DeviceUnitRepricer,
        sale_price: SalePriceParser,
        uow: TenantUnitOfWork,
    ) -> None:
        self._units = units
        self._products = products
        self._repricer = repricer
        self._sale_price = sale_price
        self._uow = uow

    async def handle(self, request: RepriceDeviceUnitsCommand) -> ResultWithData[int]:
        priced = await self._resolve(request)

        # Nothing is written until every unit has been checked. A rollback
        # would give the same end state, but failing before the first write
        # is what makes the guarantee a property of this handler rather
        # than of the transaction it happens to run in — and the operator
        # learns about the one bad handset before eight rows are flushed.
        for unit, price in priced:
            await self._repricer.set_price(unit, price, request.reason)
            await self._units.update(unit)

        await self._uow.commit()
        return ResultWithData[int].succeed_with_data(len(priced))

    async def _resolve(
        self, request: RepriceDeviceUnitsCommand
    ) -> list[tuple[DeviceUnit, Money]]:
        """Every unit with its new price, or the first reason there is none.

        Raises exactly what the single-unit route would — an unknown or
        ineligible handset (FR-2.16), a price that is not an exact amount
        in the product's currency — so a batch is refused for the same
        reasons and with the same messages as one unit.
        """
        wanted = [item.device_unit_id for item in request.prices]
        found = {unit.id: unit for unit in await self._units.find(DeviceUnitsByIds(wanted))}
        missing = [str(unit_id) for unit_id in wanted if unit_id not in found]
        if missing:
            raise NotFoundError(
                f"no such device unit in this store: {', '.join(missing)}"
            )

        resolved: list[tuple[DeviceUnit, Money]] = []
        for item in request.prices:
            unit = found[item.device_unit_id]
            unit.assert_repriceable()
            product = await self._products.get(unit.product_id)
            if product is None:
                raise NotFoundError(f"device unit {unit.id} points at a missing product")
            price = self._sale_price.parse(item.asking_price, product.currency)
            assert price is not None  # the field is required
            resolved.append((unit, price))
        return resolved
