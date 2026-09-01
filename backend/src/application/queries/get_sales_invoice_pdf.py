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

from application.common.repository import TenantDbRepository
from application.core import IRequestHandler, Query, ResultWithData
from application.dtos import RenderedDocument
from application.errors import NotFoundError
from application.localization.locale import Locale
from application.ports import (
    InvoiceRenderer,
    TenantSettingsRepository,
)
from application.specs import DeviceUnitById, SalesInvoiceById
from domain.entities import DeviceUnit, Product, SalesInvoice
from domain.enums import DocumentStatus
from domain.errors import DocumentNotConfirmedError
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    ProductModel,
    SalesInvoiceModel,
)


class GetSalesInvoicePdfQuery(Query[ResultWithData[RenderedDocument]]):
    sales_invoice_id: UUID


class GetSalesInvoicePdfHandler(
    IRequestHandler[ResultWithData[RenderedDocument], GetSalesInvoicePdfQuery]
):
    def __init__(
        self,
        invoices: TenantDbRepository[SalesInvoice, SalesInvoiceModel],
        products: TenantDbRepository[Product, ProductModel],
        units: TenantDbRepository[DeviceUnit, DeviceUnitModel],
        settings: TenantSettingsRepository,
        renderer: InvoiceRenderer,
        locale: Locale,
    ) -> None:
        self._invoices = invoices
        self._products = products
        self._units = units
        self._settings = settings
        self._renderer = renderer
        self._locale = locale

    async def handle(
        self, request: GetSalesInvoicePdfQuery
    ) -> ResultWithData[RenderedDocument]:
        invoice = await self._invoices.find_one(
            SalesInvoiceById(request.sales_invoice_id)
        )
        if invoice is None:
            raise NotFoundError(
                f"invoice {request.sales_invoice_id} does not exist in this store",
                key="not_found",
                subject_key="invoice",
            )
        if invoice.status is DocumentStatus.DRAFT:
            raise DocumentNotConfirmedError(
                f"{invoice.number} is still a draft and holds no prices — "
                "confirm it before printing it",
                key="draft_cannot_print",
                number=invoice.number,
            )

        letterhead = await self._settings.get_letterhead()
        rendered = RenderedDocument(
            filename=f"{invoice.number}.pdf",
            content_type="application/pdf",
            content=self._renderer.render(
                invoice, letterhead, await self._descriptions(invoice), self._locale
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
                unit = await self._units.find_one(DeviceUnitById(line.device_unit_id))
                if unit is not None:
                    name = f"{name}  IMEI {unit.imei}"
            descriptions[line.id] = name
        return descriptions
