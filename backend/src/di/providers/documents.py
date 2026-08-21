"""Document rendering (APP scope).

The renderer is stateless once its font is chosen, and choosing it means
touching the filesystem — so it is built once for the process rather than
per request, like the other APP-scope collaborators.
"""

from dishka import Provider, Scope, provide

from application.ports import InvoiceRenderer
from infrastructure.config import Settings
from infrastructure.documents import PdfInvoiceRenderer


class DocumentsProvider(Provider):
    @provide(scope=Scope.APP)
    def invoice_renderer(self, settings: Settings) -> InvoiceRenderer:
        return PdfInvoiceRenderer(settings.pdf_font_path)
