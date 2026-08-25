"""FR-3.2, FR-8.1: the order as a file to send the supplier.

A draft refuses to render, and for a sharper reason than the invoice's: a
draft order may still hold lines with no unit cost at all (FR-3.1), so the
page would be an order for goods at no stated price. ``_assert_priced`` is
what closes that gap at confirm, and refusing to print before then is the
same rule seen from the paperwork side.

A **cancelled** order still renders, marked as cancelled — the supplier was
sent something, and §4.3's rule that the history of a mistake is part of
the history applies to the paperwork too.
"""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import RenderedDocument
from application.ports import (
    ProductRepository,
    PurchaseOrderRenderer,
    SupplierRepository,
    TenantSettingsRepository,
)
from application.services import DocumentLoader
from domain.entities import PurchaseOrder
from domain.enums import DocumentStatus
from domain.errors import DocumentNotConfirmedError


class GetPurchaseOrderPdfQuery(Query[ResultWithData[RenderedDocument]]):
    purchase_order_id: UUID


class GetPurchaseOrderPdfHandler(
    IRequestHandler[ResultWithData[RenderedDocument], GetPurchaseOrderPdfQuery]
):
    def __init__(
        self,
        loader: DocumentLoader,
        products: ProductRepository,
        suppliers: SupplierRepository,
        settings: TenantSettingsRepository,
        renderer: PurchaseOrderRenderer,
    ) -> None:
        self._loader = loader
        self._products = products
        self._suppliers = suppliers
        self._settings = settings
        self._renderer = renderer

    async def handle(
        self, request: GetPurchaseOrderPdfQuery
    ) -> ResultWithData[RenderedDocument]:
        order = await self._loader.load_order(request.purchase_order_id)
        if order.status is DocumentStatus.DRAFT:
            raise DocumentNotConfirmedError(
                f"{order.number} is still a draft and its lines may hold no cost — "
                "confirm it before printing it"
            )

        supplier = await self._suppliers.get(order.supplier_id)
        content = self._renderer.render(
            order,
            await self._settings.get_letterhead(),
            None if supplier is None else supplier.name,
            await self._descriptions(order),
        )
        return ResultWithData[RenderedDocument].succeed_with_data(
            RenderedDocument(
                filename=f"{order.number}.pdf",
                content_type="application/pdf",
                content=content,
            )
        )

    async def _descriptions(self, order: PurchaseOrder) -> dict[UUID, str]:
        descriptions: dict[UUID, str] = {}
        for line in order.lines:
            product = await self._products.get(line.product_id)
            descriptions[line.id] = (
                str(line.product_id) if product is None else product.name
            )
        return descriptions
