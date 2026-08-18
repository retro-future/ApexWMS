"""What one scan of an unknown code resolves to — PRD §6, FR-7.1, FR-7.2.

The scanner is a keyboard wedge: it types a string and presses Enter, and
it has no idea whether what it just read was an IMEI off the back of a
handset or a barcode off an accessory's box. So the client sends the
string and **the server says which kind it found** — one call, one round
trip, because §6 puts the whole latency budget on this endpoint.

The two branches carry the payloads the rest of the API already returns
rather than a flattened summary of their own. That is what makes the cost
shaping of FR-1.7 automatic: ``DeviceUnitData`` already omits acquisition
cost and ``cashPaid`` without ``Permission.Cost.View``, so a Seller's
lookup cannot leak a margin no matter what the client renders.
"""

from __future__ import annotations

from enum import StrEnum

from application.core import CamelModel
from application.models.device_unit import DeviceUnitData
from application.models.product import ProductData


class ScanKind(StrEnum):
    DEVICE = "device"
    PRODUCT = "product"


class ScanLookupData(CamelModel):
    kind: ScanKind
    # Exactly one of these is populated, chosen by ``kind``. A code that
    # matched nothing never reaches here — it is a 404 (FR-7.4).
    device: DeviceUnitData | None = None
    product: ProductData | None = None

    @classmethod
    def for_device(cls, device: DeviceUnitData) -> ScanLookupData:
        return cls(kind=ScanKind.DEVICE, device=device)

    @classmethod
    def for_product(cls, product: ProductData) -> ScanLookupData:
        return cls(kind=ScanKind.PRODUCT, product=product)
