"""Document rendering (APP scope).

A renderer is stateless once its font is chosen, and choosing it means
touching the filesystem — so the factory that resolves it is built once for
the process, like the other APP-scope collaborators, and hands each render
its own mutable page.
"""

from dishka import Provider, Scope, provide

from application.ports import (
    InvoiceRenderer,
    LabelRenderer,
    MonthEndReportRenderer,
    PurchaseOrderRenderer,
    SupplierReturnRenderer,
)
from infrastructure.config import Settings
from infrastructure.documents import (
    DocumentPageFactory,
    PdfInvoiceRenderer,
    PdfLabelRenderer,
    PdfMonthEndReportRenderer,
    PdfPurchaseOrderRenderer,
    PdfSupplierReturnRenderer,
)


class DocumentsProvider(Provider):
    scope = Scope.APP

    @provide
    def pages(self, settings: Settings) -> DocumentPageFactory:
        return DocumentPageFactory(settings.pdf_font_path)

    @provide
    def invoice_renderer(self, pages: DocumentPageFactory) -> InvoiceRenderer:
        return PdfInvoiceRenderer(pages)

    @provide
    def purchase_order_renderer(
        self, pages: DocumentPageFactory
    ) -> PurchaseOrderRenderer:
        return PdfPurchaseOrderRenderer(pages)

    @provide
    def supplier_return_renderer(
        self, pages: DocumentPageFactory
    ) -> SupplierReturnRenderer:
        return PdfSupplierReturnRenderer(pages)

    @provide
    def month_end_renderer(self, pages: DocumentPageFactory) -> MonthEndReportRenderer:
        return PdfMonthEndReportRenderer(pages)

    @provide
    def label_renderer(self, settings: Settings) -> LabelRenderer:
        return PdfLabelRenderer(settings.pdf_font_path)
