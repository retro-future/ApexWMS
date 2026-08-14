"""Turning requested lines into document lines (PRD §5.3, FR-2.7).

A line does not state its own currency or its own tracking type — both come
from the product it names (§4.5 rule 3, §4.1), and this is where that
lookup happens once for the four handlers that need it: creating and
editing a Purchase Order, creating and editing a Goods Receipt.

Which is also why an order may hold a USD phone line and a UZS accessory
line at the same time and still have no currency of its own. Each line is
denominated by its product, and the document reports one subtotal per
currency rather than a total.
"""

from collections.abc import Sequence
from uuid import UUID, uuid4

from application.dtos import LineInput
from application.errors import NotFoundError
from application.ports import ProductRepository
from domain.entities import GoodsReceiptLine, Product, PurchaseOrderLine
from domain.enums import TrackingType
from domain.value_objects import Money


class DocumentLineBuilder:
    def __init__(self, products: ProductRepository) -> None:
        self._products = products

    async def order_lines(
        self, order_id: UUID, items: Sequence[LineInput]
    ) -> list[PurchaseOrderLine]:
        """FR-3.1: a PO line may arrive with no price at all.

        An Owner may raise an order before a supplier has quoted a price;
        it is filled in afterward, one line at a time, while the order is
        still a draft. ``PurchaseOrder.confirm()`` is what refuses to let
        an unpriced line through.
        """
        lines: list[PurchaseOrderLine] = []
        for item in items:
            product = await self._product(item.product_id)
            lines.append(
                PurchaseOrderLine(
                    id=uuid4(),
                    purchase_order_id=order_id,
                    product_id=product.id,
                    quantity=item.quantity,
                    unit_cost=(
                        None
                        if item.unit_cost is None
                        else Money.from_major(item.unit_cost, product.currency)
                    ),
                    currency=product.currency,
                    tracking_type=product.tracking_type,
                )
            )
        return lines

    async def receipt_lines(
        self, receipt_id: UUID, items: Sequence[LineInput]
    ) -> list[GoodsReceiptLine]:
        """A receipt line may arrive with no cost at all.

        A Storekeeper opens the receipt and scans; an Owner or Manager
        states what was paid (FR-3.4b). The draft holds the gap, and
        ``GoodsReceipt.confirm()`` is what refuses to let it through
        (FR-3.12).
        """
        lines: list[GoodsReceiptLine] = []
        for item in items:
            product = await self._product(item.product_id)
            serial = product.tracking_type is TrackingType.SERIAL
            lines.append(
                GoodsReceiptLine(
                    id=uuid4(),
                    goods_receipt_id=receipt_id,
                    product_id=product.id,
                    quantity=item.quantity,
                    # A serialized line prices each handset individually, so
                    # a cost stated here is dropped rather than stored where
                    # nothing would read it.
                    unit_cost=(
                        None
                        if serial or item.unit_cost is None
                        else Money.from_major(item.unit_cost, product.currency)
                    ),
                    tracking_type=product.tracking_type,
                    currency=product.currency,
                )
            )
        return lines

    async def _product(self, product_id: UUID) -> Product:
        product = await self._products.get(product_id)
        if product is None:
            raise NotFoundError(f"product {product_id} does not exist in this store")
        return product
