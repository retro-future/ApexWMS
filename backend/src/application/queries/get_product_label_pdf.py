"""A product's shelf label as a PDF (FR-2.3, FR-8.1).

An accessory with a barcode gets an EAN-13 label; everything else (a
phone, or an accessory with no barcode) gets a Code128 of the SKU, which
``/scan/lookup`` resolves the same way.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import ProductLabel, RenderedDocument
from application.errors import NotFoundError
from application.ports import LabelRenderer, TenantSettingsRepository
from domain.entities import Product
from domain.enums import LabelLayout
from infrastructure.persistence.tenant.models import ProductModel

_MAX_COPIES = 24


class GetProductLabelPdfQuery(Query[ResultWithData[RenderedDocument]]):
    product_id: UUID
    layout: LabelLayout = LabelLayout.SINGLE
    copies: int = _MAX_COPIES


class GetProductLabelPdfHandler(
    IRequestHandler[ResultWithData[RenderedDocument], GetProductLabelPdfQuery]
):
    def __init__(
        self,
        products: TenantDbRepository[Product, ProductModel],
        settings: TenantSettingsRepository,
        renderer: LabelRenderer,
    ) -> None:
        self._products = products
        self._settings = settings
        self._renderer = renderer

    async def handle(
        self, request: GetProductLabelPdfQuery
    ) -> ResultWithData[RenderedDocument]:
        product = await self._products.get(request.product_id)
        if product is None:
            raise NotFoundError(
                "no such product in this store",
                key="not_found",
                subject_key="product",
            )

        if product.barcode is not None:
            label = ProductLabel(
                product_name=product.name,
                code_value=str(product.barcode),
                code_symbology="ean13",
            )
        else:
            label = ProductLabel(
                product_name=product.name,
                code_value=str(product.sku),
                code_symbology="code128",
            )
        content = self._renderer.render(
            label,
            await self._settings.get_letterhead(),
            request.layout,
            max(1, min(request.copies, _MAX_COPIES)),
        )
        return ResultWithData[RenderedDocument].succeed_with_data(
            RenderedDocument(
                filename=f"{product.sku}-label.pdf",
                content_type="application/pdf",
                content=content,
            )
        )
