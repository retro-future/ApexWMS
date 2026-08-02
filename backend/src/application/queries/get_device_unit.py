"""Read one handset — PRD §8, FR-1.7, FR-7.2.

``DeviceUnitData`` omits cost, margin and ``cashPaid`` for anyone without
``Permission.Cost.View``. **This is response-shaping, not UI hiding**
(FR-1.7): a Storekeeper or a Seller who reads this endpoint never receives
the figures at all, so there is nothing in the payload for a curious
client to render.

The price it *would* sell at is always present, because that is what the
Seller actually needs at the counter (FR-7.2) — and where the resolution
rule refuses (a used handset nobody has priced), it says so explicitly
rather than reporting zero or the catalog price.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from application.core import CamelModel, IRequestHandler, Query, ResultWithData
from application.dtos import CurrentUser
from application.errors import NotFoundError
from application.ports import DeviceUnitRepository, ProductRepository
from domain.entities import DeviceUnit, Product
from domain.enums import DeviceCondition, DeviceStatus
from domain.permissions import Permission
from domain.services import resolve_sale_price_or_none
from domain.value_objects import Currency


class DeviceUnitData(CamelModel):
    id: UUID
    imei: str
    imei2: str | None
    serial_number: str | None
    product_id: UUID
    sku: str
    product_name: str
    status: DeviceStatus
    condition: DeviceCondition
    location_id: UUID | None
    currency: Currency
    # The resolved price (FR-2.14), or None where the rule refuses. A
    # Seller reads this; ``resolvedPrice is None`` is the counter's cue
    # that an Owner or Manager has to price the handset first.
    asking_price: Decimal | None
    resolved_price: Decimal | None
    resolved_price_minor: int | None
    created_at: datetime
    # --- Permission.Cost.View only (FR-1.7) ---
    acquisition_cost: Decimal | None = None
    acquisition_cost_minor: int | None = None
    # "paid 4 200 000 so'm · booked at $330" — a string, never a number,
    # so no caller can add it to anything (§4.5b, FR-3.4d).
    cash_paid: str | None = None

    @classmethod
    def from_unit(
        cls, unit: DeviceUnit, product: Product, *, show_cost: bool
    ) -> DeviceUnitData:
        resolved = resolve_sale_price_or_none(unit, product)
        data = cls(
            id=unit.id,
            imei=str(unit.imei),
            imei2=str(unit.imei2) if unit.imei2 else None,
            serial_number=unit.serial_number,
            product_id=unit.product_id,
            sku=str(product.sku),
            product_name=product.name,
            status=unit.status,
            condition=unit.condition,
            location_id=unit.location_id,
            currency=unit.currency,
            asking_price=unit.asking_price.as_major() if unit.asking_price else None,
            resolved_price=resolved.as_major() if resolved else None,
            resolved_price_minor=resolved.amount_minor if resolved else None,
            created_at=unit.created_at,
        )
        if not show_cost:
            return data
        return data.model_copy(
            update={
                "acquisition_cost": unit.acquisition_cost.as_major(),
                "acquisition_cost_minor": unit.acquisition_cost.amount_minor,
                "cash_paid": unit.cash_paid_display(),
            }
        )


class GetDeviceUnitQuery(Query[ResultWithData[DeviceUnitData]]):
    device_unit_id: UUID


class GetDeviceUnitHandler(IRequestHandler[ResultWithData[DeviceUnitData], GetDeviceUnitQuery]):
    def __init__(
        self,
        units: DeviceUnitRepository,
        products: ProductRepository,
        current: CurrentUser,
    ) -> None:
        self._units = units
        self._products = products
        self._current = current

    async def handle(self, request: GetDeviceUnitQuery) -> ResultWithData[DeviceUnitData]:
        unit, product = await load_unit_with_product(
            self._units, self._products, request.device_unit_id
        )
        return ResultWithData[DeviceUnitData].succeed_with_data(
            DeviceUnitData.from_unit(
                unit,
                product,
                show_cost=Permission.COST_VIEW in self._current.permissions,
            )
        )


async def load_unit_with_product(
    units: DeviceUnitRepository, products: ProductRepository, device_unit_id: UUID
) -> tuple[DeviceUnit, Product]:
    """A handset and its catalog row, or ``NotFoundError``.

    Every unit operation needs both — the product carries the currency the
    unit's amounts are denominated in (§4.5 rule 3) and the catalog price
    the resolution rule may fall back to — so the pair is loaded in one
    place rather than in each handler.
    """
    unit = await units.get(device_unit_id)
    if unit is None:
        raise NotFoundError("no such device unit in this store")
    product = await products.get(unit.product_id)
    if product is None:
        # Impossible through a foreign key, and worth saying plainly rather
        # than failing later with an attribute error on None.
        raise NotFoundError(f"device unit {device_unit_id} points at a missing product")
    return unit, product
