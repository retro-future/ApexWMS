"""Load a handset with its catalog row — shared by every unit-scoped use case."""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.errors import NotFoundError
from application.specs import DeviceUnitById, DeviceUnitByImei
from domain.entities import DeviceUnit, Product
from infrastructure.persistence.tenant.models import DeviceUnitModel, ProductModel


class DeviceUnitLoader:
    def __init__(
        self,
        units: TenantDbRepository[DeviceUnit, DeviceUnitModel],
        products: TenantDbRepository[Product, ProductModel],
    ) -> None:
        self._units = units
        self._products = products

    async def load(self, device_unit_id: UUID) -> tuple[DeviceUnit, Product]:
        """A handset and its catalog row, or ``NotFoundError``.

        Every unit operation needs both — the product carries the currency the
        unit's amounts are denominated in (§4.5 rule 3) and the catalog price
        the resolution rule may fall back to — so the pair is loaded in one
        place rather than in each handler.
        """
        unit = await self._units.find_one(DeviceUnitById(device_unit_id))
        if unit is None:
            raise NotFoundError("no such device unit in this store")
        return unit, await self._catalog_row_of(unit)

    async def load_by_imei(self, imei: str) -> tuple[DeviceUnit, Product] | None:
        """The same pair, found by IMEI, or ``None`` when no handset has it.

        A miss is a return value rather than an error because the caller
        scanning a code does not yet know it *was* an IMEI (FR-7.1): it has
        barcodes and SKUs left to try before anyone may say the code is
        unknown.
        """
        unit = await self._units.find_one(DeviceUnitByImei(imei))
        if unit is None:
            return None
        return unit, await self._catalog_row_of(unit)

    async def _catalog_row_of(self, unit: DeviceUnit) -> Product:
        product = await self._products.get(unit.product_id)
        if product is None:
            # Impossible through a foreign key, and worth saying plainly rather
            # than failing later with an attribute error on None.
            raise NotFoundError(f"device unit {unit.id} points at a missing product")
        return product
