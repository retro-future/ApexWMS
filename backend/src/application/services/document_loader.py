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
    PurchaseOrderRepository,
    SalesInvoiceRepository,
)
from domain.entities import GoodsReceipt, PurchaseOrder, SalesInvoice


class DocumentLoader:
    def __init__(
        self,
        orders: PurchaseOrderRepository,
        receipts: GoodsReceiptRepository,
        invoices: SalesInvoiceRepository,
    ) -> None:
        self._orders = orders
        self._receipts = receipts
        self._invoices = invoices

    async def load_order(self, order_id: UUID) -> PurchaseOrder:
        order = await self._orders.get(order_id)
        if order is None:
            raise NotFoundError(f"purchase order {order_id} does not exist in this store")
        return order

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
