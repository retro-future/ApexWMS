"""FR-5.3, FR-8.1: the note that goes back with the goods.

A draft refuses to render. Nothing has left the shelf yet (§4.4), so the
note would describe a delivery that is not happening, and the handsets it
names may still be sold from under it before confirm.

A **cancelled** return still renders, marked as cancelled.
"""

from uuid import UUID

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import RenderedDocument
from application.errors import NotFoundError
from application.ports import (
    LocationRepository,
    ProductRepository,
    SupplierReturnRenderer,
    TenantSettingsRepository,
)
from application.specs import SupplierById, SupplierReturnById
from domain.entities import Supplier, SupplierReturn
from domain.enums import DocumentStatus
from domain.errors import DocumentNotConfirmedError
from infrastructure.persistence.tenant.models import SupplierModel, SupplierReturnModel


class GetSupplierReturnPdfQuery(Query[ResultWithData[RenderedDocument]]):
    supplier_return_id: UUID


class GetSupplierReturnPdfHandler(
    IRequestHandler[ResultWithData[RenderedDocument], GetSupplierReturnPdfQuery]
):
    def __init__(
        self,
        returns: TenantDbRepository[SupplierReturn, SupplierReturnModel],
        products: ProductRepository,
        suppliers: TenantDbRepository[Supplier, SupplierModel],
        locations: LocationRepository,
        settings: TenantSettingsRepository,
        renderer: SupplierReturnRenderer,
    ) -> None:
        self._returns = returns
        self._products = products
        self._suppliers = suppliers
        self._locations = locations
        self._settings = settings
        self._renderer = renderer

    async def handle(
        self, request: GetSupplierReturnPdfQuery
    ) -> ResultWithData[RenderedDocument]:
        document = await self._returns.find_one(
            SupplierReturnById(request.supplier_return_id)
        )
        if document is None:
            raise NotFoundError(
                f"supplier return {request.supplier_return_id} does not exist in this store"
            )
        if document.status is DocumentStatus.DRAFT:
            raise DocumentNotConfirmedError(
                f"{document.number} is still a draft and nothing has left the shelf — "
                "confirm it before printing it"
            )

        supplier = await self._suppliers.find_one(SupplierById(document.supplier_id))
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
