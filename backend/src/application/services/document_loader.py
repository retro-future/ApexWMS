"""Fetching a document, or saying plainly that it is not there.

Every document handler begins by loading the one document they are about to act
on, and a repository returns ``None`` rather than raising — deliberately,
because "and if the row is absent?" is a question the caller answers.
Here the answer is always the same, so it is answered once.
"""

from uuid import UUID

from application.errors import NotFoundError
from application.ports import (
    GoodsReceiptRepository,
    SalesInvoiceRepository,
    StockCountRepository,
    WriteOffRepository,
)
from domain.entities import (
    GoodsReceipt,
    SalesInvoice,
    StockCount,
    WriteOff,
)


class DocumentLoader:
    def __init__(
        self,
        receipts: GoodsReceiptRepository,
        invoices: SalesInvoiceRepository,
        write_offs: WriteOffRepository,
        counts: StockCountRepository,
    ) -> None:
        self._receipts = receipts
        self._invoices = invoices
        self._write_offs = write_offs
        self._counts = counts

    async def load_receipt(self, receipt_id: UUID) -> GoodsReceipt:
        receipt = await self._receipts.get(receipt_id)
        if receipt is None:
            raise NotFoundError(f"goods receipt {receipt_id} does not exist in this store")
        return receipt

    async def load_invoice(self, invoice_id: UUID) -> SalesInvoice:
        invoice = await self._invoices.get(invoice_id)
        if invoice is None:
            raise NotFoundError(f"invoice {invoice_id} does not exist in this store")
        return invoice

    async def load_write_off(self, write_off_id: UUID) -> WriteOff:
        write_off = await self._write_offs.get(write_off_id)
        if write_off is None:
            raise NotFoundError(f"write-off {write_off_id} does not exist in this store")
        return write_off

    async def load_count(self, count_id: UUID) -> StockCount:
        count = await self._counts.get(count_id)
        if count is None:
            raise NotFoundError(f"stock count {count_id} does not exist in this store")
        return count
