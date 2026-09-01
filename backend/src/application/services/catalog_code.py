"""Turning a per-tenant counter into a unique SKU or in-store barcode.

SKUs read ``PH-000001`` for a phone and ``AC-000001`` for an accessory:
the prefix tells the two apart on a shelf label and survives a product
with no brand or model. The barcode is an EAN-13 in the GS1 ``20``
"restricted distribution" range, correct for a code that is only unique
inside one store.

The counter alone cannot guarantee uniqueness — a manager may have typed
``PH-000001`` by hand — so a generated code is checked against the catalog
and the counter is bumped again on the rare hit.
"""

from application.common.repository import TenantDbRepository
from application.errors import BarcodeGenerationError, SkuGenerationError
from application.ports import CatalogCodeAllocator
from application.specs import ProductByBarcode, ProductBySku
from domain.entities import Product
from domain.enums import CatalogCodeKind, TrackingType
from domain.value_objects import SKU, Barcode
from infrastructure.persistence.tenant.models import ProductModel

_MAX_ATTEMPTS = 5

_SKU_KIND: dict[TrackingType, CatalogCodeKind] = {
    TrackingType.SERIAL: CatalogCodeKind.SKU_SERIAL,
    TrackingType.QUANTITY: CatalogCodeKind.SKU_QUANTITY,
}
_SKU_PREFIX: dict[TrackingType, str] = {
    TrackingType.SERIAL: "PH",
    TrackingType.QUANTITY: "AC",
}


class CatalogCodeGenerator:
    def __init__(
        self,
        allocator: CatalogCodeAllocator,
        products: TenantDbRepository[Product, ProductModel],
    ) -> None:
        self._allocator = allocator
        self._products = products

    async def next_sku(self, tracking_type: TrackingType) -> SKU:
        for _ in range(_MAX_ATTEMPTS):
            n = await self._allocator.next(_SKU_KIND[tracking_type])
            sku = SKU(f"{_SKU_PREFIX[tracking_type]}-{n:06d}")
            if not await self._products.exists(ProductBySku(str(sku))):
                return sku
        raise SkuGenerationError("could not allocate a free SKU after several tries")

    async def next_barcode(self) -> Barcode:
        for _ in range(_MAX_ATTEMPTS):
            n = await self._allocator.next(CatalogCodeKind.BARCODE)
            barcode = Barcode.from_payload(f"20{n:010d}")
            if not await self._products.exists(ProductByBarcode(str(barcode))):
                return barcode
        raise BarcodeGenerationError("could not allocate a free barcode after several tries")
