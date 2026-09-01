"""Which per-tenant catalog counter to draw the next number from.

A SKU counter per tracking type keeps the two prefixes (``PH-``/``AC-``)
independently dense; the barcode counter feeds the store's own EAN-13
range.
"""

from enum import StrEnum


class CatalogCodeKind(StrEnum):
    SKU_SERIAL = "sku_serial"
    SKU_QUANTITY = "sku_quantity"
    BARCODE = "barcode"
