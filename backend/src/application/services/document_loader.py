"""Fetching a document, or saying plainly that it is not there.

Eleven M4 handlers begin by loading the one document they are about to act
on, and a repository returns ``None`` rather than raising — deliberately,
because "and if the row is absent?" is a question the caller answers.
Here the answer is always the same, so it is answered once.
"""

from uuid import UUID

from application.errors import NotFoundError
from application.ports import GoodsReceiptRepository, PurchaseOrderRepository
from domain.entities import GoodsReceipt, PurchaseOrder


class DocumentLoader:
    def __init__(
        self, orders: PurchaseOrderRepository, receipts: GoodsReceiptRepository
    ) -> None:
        self._orders = orders
        self._receipts = receipts

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
