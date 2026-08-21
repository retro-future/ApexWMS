"""FR-4.6, FR-8.1: the invoice as a file the customer can take away.

A draft refuses to render. It holds no prices at all (FR-4.5b1), so the
page would be a list of items with empty money columns — a document that
looks like a receipt and is not one. The refusal reuses
``DocumentNotConfirmedError``, the same 409 a cancel-before-confirm gets,
because it is the same fact: the sale has not happened yet.

A **cancelled** invoice still renders, marked as cancelled. It describes
something that did happen and was then reversed, and §4.3's rule that the
history of a mistake is part of the history applies to the paperwork too.

Rendered on demand, never stored. A confirmed document is immutable and
its lines carry their own snapshotted prices (FR-4.5b), so the file is the
same every time it is asked for.
"""

from uuid import UUID

from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import RenderedDocument
from application.ports import (
    DeviceUnitRepository,
    InvoiceRenderer,
    ProductRepository,
    TenantSettingsRepository,
)
from application.services import DocumentLoader
from domain.entities import SalesInvoice
from domain.enums import DocumentStatus
from domain.errors import DocumentNotConfirmedError


class GetSalesInvoicePdfQuery(Query[ResultWithData[RenderedDocument]]):
    sales_invoice_id: UUID


class GetSalesInvoicePdfHandler(
    IRequestHandler[ResultWithData[RenderedDocument], GetSalesInvoicePdfQuery]
):
    def __init__(
        self,
        loader: DocumentLoader,
        products: ProductRepository,
        units: DeviceUnitRepository,
        settings: TenantSettingsRepository,
        renderer: InvoiceRenderer,
    ) -> None:
        self._loader = loader
        self._products = products
        self._units = units
        self._settings = settings
        self._renderer = renderer

    async def handle(
        self, request: GetSalesInvoicePdfQuery
    ) -> ResultWithData[RenderedDocument]:
        invoice = await self._loader.load_invoice(request.sales_invoice_id)
        if invoice.status is DocumentStatus.DRAFT:
            raise DocumentNotConfirmedError(
                f"{invoice.number} is still a draft and holds no prices — "
                "confirm it before printing it"
            )

        letterhead = await self._settings.get_letterhead()
        rendered = RenderedDocument(
            filename=f"{invoice.number}.pdf",
            content_type="application/pdf",
            content=self._renderer.render(
                invoice, letterhead, await self._descriptions(invoice)
            ),
        )
        return ResultWithData[RenderedDocument].succeed_with_data(rendered)

    async def _descriptions(self, invoice: SalesInvoice) -> dict[UUID, str]:
        """What each line reads as on the page.

        The model, and the IMEI after it where the line names a specific
        handset — FR-8.1's demo is *"print a real invoice with an IMEI on
        it"*, and that IMEI is what makes the paper match the phone in the
        customer's hand.
        """
        descriptions: dict[UUID, str] = {}
        for line in invoice.lines:
            product = await self._products.get(line.product_id)
            name = str(line.product_id) if product is None else product.name
            if line.device_unit_id is not None:
                unit = await self._units.get(line.device_unit_id)
                if unit is not None:
                    name = f"{name}  IMEI {unit.imei}"
            descriptions[line.id] = name
        return descriptions
