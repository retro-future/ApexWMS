"""Resolving one beep onto a Supplier Return or a Write-Off (PRD §6, FR-5.2).

Both documents take goods off the shelf, so both scans ask the same
questions of a scanned string: is this an IMEI or a barcode, does the store
hold the thing it names, and is it here rather than at another location. A
return asks one more — did this handset come from the supplier it is going
back to (FR-5.2b) — which a write-off cannot ask, having no supplier.

The refusals happen **on the scan that caused them**, while the operator is
still holding the phone (§6): a handset already sold cannot also be sent
back, and discovering that when a ten-unit return is submitted is the
workflow §6 exists to rule out.

``RemovalPoster`` asks the same of the live unit again at confirm, and that
is not redundant: a draft reserves nothing, and the phone can be sold from
under an open return.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.errors import NotFoundError
from application.services.device_unit_loader import DeviceUnitLoader
from application.services.unit_origin import UnitOriginGuard
from application.specs import ProductByBarcode, ProductBySku
from domain.entities import DeviceUnit, Product
from domain.enums import DeviceStatus, TrackingType
from domain.errors import InvalidIMEIError, UnitNotRemovableError, WrongLocationError
from domain.value_objects import IMEI
from infrastructure.persistence.tenant.models import ProductModel


class RemovalScanner:
    def __init__(
        self,
        units: DeviceUnitLoader,
        products: TenantDbRepository[Product, ProductModel],
        origin: UnitOriginGuard,
    ) -> None:
        self._units = units
        self._products = products
        self._origin = origin

    async def resolve(
        self, code: str, *, location_id: UUID, number: str, supplier_id: UUID | None
    ) -> tuple[Product, DeviceUnit | None]:
        """What this scanned string names, once it is known to be movable.

        Returns the catalog row and, for a serialized scan, the handset —
        ``None`` for an accessory, which has no per-unit identity (§4.1).

        ``supplier_id`` is ``None`` for a write-off, which sends goods
        nowhere and so has no origin to match (FR-5.2b).
        """
        found = await self._as_device(code)
        if found is not None:
            unit, product = found
            self._assert_removable(unit, location_id=location_id, number=number)
            if supplier_id is not None:
                await self._origin.assert_from_supplier(
                    unit, supplier_id=supplier_id, number=number
                )
            return product, unit

        product = await self._as_product(code)
        if product.tracking_type is TrackingType.SERIAL:
            raise UnitNotRemovableError(
                f"{product.sku} is a serialized model, and {number} moves one named "
                "handset — scan the phone's IMEI rather than the model's barcode"
            )
        return product, None

    async def _as_device(self, code: str) -> tuple[DeviceUnit, Product] | None:
        """A scanned string is an IMEI only if it parses as one.

        ``InvalidIMEIError`` is swallowed rather than raised: a 13-digit
        barcode is not a malformed IMEI, it is a barcode, and the caller
        never said which it was sending (§6).
        """
        try:
            imei = IMEI.parse(code)
        except InvalidIMEIError:
            return None
        return await self._units.load_by_imei(str(imei))

    async def _as_product(self, code: str) -> Product:
        product = await self._products.find_one(ProductByBarcode(code))
        if product is None:
            product = await self._products.find_one(ProductBySku(code))
        if product is None:
            raise NotFoundError(f"nothing in this store is identified by {code!r}")
        return product

    @staticmethod
    def _assert_removable(unit: DeviceUnit, *, location_id: UUID, number: str) -> None:
        if unit.status is not DeviceStatus.IN_STOCK:
            raise UnitNotRemovableError(
                f"IMEI {unit.imei} is {unit.status.value} and is not on the shelf, "
                f"so {number} cannot move it (FR-5.2)"
            )
        if unit.location_id != location_id:
            raise WrongLocationError(
                f"IMEI {unit.imei} is held at another location, and {number} moves "
                "stock from its own"
            )
