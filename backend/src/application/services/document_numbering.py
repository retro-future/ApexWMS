"""Human-readable document numbers — ``PO-2026-0001`` (PRD §4.4).

The number is what a person says out loud on the phone to a supplier, so
it is not the UUID and it restarts each year. It is handed out when the
draft is created rather than at confirm, so an operator can name the
document they are working on; a deleted draft therefore leaves a gap in
the sequence, which is the honest outcome and not a problem to solve.

Uniqueness comes from the allocator holding a row lock, not from this
class: two storekeepers opening a receipt at the same counter in the same
second must not be handed the same number.
"""

from application.ports import Clock, DocumentNumberAllocator
from domain.enums import DocumentType

_PREFIXES: dict[DocumentType, str] = {
    DocumentType.PURCHASE_ORDER: "PO",
    DocumentType.GOODS_RECEIPT: "GR",
    DocumentType.SALES_INVOICE: "INV",
    DocumentType.SUPPLIER_RETURN: "SR",
    DocumentType.STOCK_COUNT: "SC",
    DocumentType.WRITE_OFF: "WO",
}


class DocumentNumberer:
    def __init__(self, numbers: DocumentNumberAllocator, clock: Clock) -> None:
        self._numbers = numbers
        self._clock = clock

    async def next(self, document_type: DocumentType) -> str:
        year = self._clock.now().year
        sequence = await self._numbers.next_number(document_type, year)
        return f"{_PREFIXES[document_type]}-{year}-{sequence:04d}"
