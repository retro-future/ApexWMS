"""What a product's shelf label prints, handed from the query to the renderer."""

from dataclasses import dataclass
from typing import Literal

Symbology = Literal["ean13", "code128"]


@dataclass(frozen=True, slots=True)
class ProductLabel:
    """One label's content, for a product or a single handset.

    ``code_value`` is an accessory's EAN-13 when it has one, otherwise a
    Code128 of the SKU (a phone model carries no stored barcode, FR-2.3) or
    of a handset's own IMEI. ``/scan/lookup`` resolves all three the same way.
    """

    product_name: str
    code_value: str
    code_symbology: Symbology
