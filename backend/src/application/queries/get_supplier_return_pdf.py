"""FR-5.3, FR-8.1: the note that goes back with the goods.

A draft refuses to render. Nothing has left the shelf yet (§4.4), so the
note would describe a delivery that is not happening, and the handsets it
names may still be sold from under it before confirm.

A **cancelled** return still renders, marked as cancelled.
"""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import RenderedDocument
from application.ports import (
    LocationRepository,
    ProductRepository,
    SupplierRepository,
    SupplierReturnRenderer,
    TenantSettingsRepository,
)
from application.services import DocumentLoader
from domain.entities import SupplierReturn
from domain.enums import DocumentStatus
from domain.errors import DocumentNotConfirmedError


class GetSupplierReturnPdfQuery(Query[ResultWithData[RenderedDocument]]):
    supplier_return_id: UUID


class GetSupplierReturnPdfHandler(
    IRequestHandler[ResultWithData[RenderedDocument], GetSupplierReturnPdfQuery]
):
    def __init__(
        self,
        loader: DocumentLoader,
        products: ProductRepository,
        suppliers: SupplierRepository,
        locations: LocationRepository,
        settings: TenantSettingsRepository,
        renderer: SupplierReturnRenderer,
    ) -> None:
        self._loader = loader
        self._products = products
        self._suppliers = suppliers
        self._locations = locations
        self._settings = settings
        self._renderer = renderer

    async def handle(
        self, request: GetSupplierReturnPdfQuery
    ) -> ResultWithData[RenderedDocument]:
        document = await self._loader.load_return(request.supplier_return_id)
        if document.status is DocumentStatus.DRAFT:
            raise DocumentNotConfirmedError(
                f"{document.number} is still a draft and nothing has left the shelf — "
                "confirm it before printing it"
            )

        supplier = await self._suppliers.get(document.supplier_id)
        location = await self._locations.get(document.location_id)
        content = self._renderer.render(
            document,
            await self._settings.get_letterhead(),
            None if supplier is None else supplier.name,
            None if location is None else location.name,
            await self._descriptions(document),
        )
        return ResultWithData[RenderedDocument].succeed_with_data(
            RenderedDocument(
                filename=f"{document.number}.pdf",
                content_type="application/pdf",
                content=content,
            )
        )

    async def _descriptions(self, document: SupplierReturn) -> dict[UUID, str]:
        descriptions: dict[UUID, str] = {}
        for line in document.lines:
            product = await self._products.get(line.product_id)
            descriptions[line.id] = (
                str(line.product_id) if product is None else product.name
            )
        return descriptions
