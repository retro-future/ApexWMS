"""Proving which supplier a handset came from (PRD FR-5.2b).

A unit's origin is the goods receipt that put it in stock, and that receipt
names the supplier. Nothing stores the supplier on the unit itself, so the
question needs a second read, which is why it lives here rather than on
``SupplierReturn.confirm()``.

Anything without a supplier receipt behind it is refused: a trade-in names
no supplier by design (FR-3.3b), and a handset a stock count discovered has
no receipt at all (FR-6.4b).
"""

from uuid import UUID

from application.ports import GoodsReceiptRepository
from domain.entities import DeviceUnit
from domain.enums import DocumentType
from domain.errors import UnitNotFromSupplierError


class UnitOriginGuard:
    def __init__(self, receipts: GoodsReceiptRepository) -> None:
        self._receipts = receipts

    async def assert_from_supplier(
        self, unit: DeviceUnit, *, supplier_id: UUID, number: str
    ) -> None:
        if (
            unit.source_document_type is not DocumentType.GOODS_RECEIPT
            or unit.source_document_id is None
        ):
            raise UnitNotFromSupplierError(
                f"IMEI {unit.imei} did not enter stock through a supplier "
                f"delivery, so {number} cannot send it back (FR-5.2b)"
            )

        origin = await self._receipts.supplier_of(unit.source_document_id)
        if origin != supplier_id:
            raise UnitNotFromSupplierError(
                f"IMEI {unit.imei} came from another supplier, and {number} "
                "sends goods back to the one it names (FR-5.2b)"
            )
