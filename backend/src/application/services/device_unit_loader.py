"""Load a handset with its catalog row — shared by every unit-scoped use case."""

from uuid import UUID

from application.errors import NotFoundError
from application.ports import DeviceUnitRepository, ProductRepository
from domain.entities import DeviceUnit, Product


class DeviceUnitLoader:
    def __init__(self, units: DeviceUnitRepository, products: ProductRepository) -> None:
        self._units = units
        self._products = products

    async def load(self, device_unit_id: UUID) -> tuple[DeviceUnit, Product]:
        """A handset and its catalog row, or ``NotFoundError``.

        Every unit operation needs both — the product carries the currency the
        unit's amounts are denominated in (§4.5 rule 3) and the catalog price
        the resolution rule may fall back to — so the pair is loaded in one
        place rather than in each handler.
        """
        unit = await self._units.get(device_unit_id)
        if unit is None:
            raise NotFoundError("no such device unit in this store")
        product = await self._products.get(unit.product_id)
        if product is None:
            # Impossible through a foreign key, and worth saying plainly rather
            # than failing later with an attribute error on None.
            raise NotFoundError(f"device unit {device_unit_id} points at a missing product")
        return unit, product
