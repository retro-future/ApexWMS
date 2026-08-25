"""The invoice, on paper (PRD §5.8, FR-8.1, FR-4.6).

Rendered on demand rather than stored at confirm. A confirmed document is
immutable (§4.4) and its lines carry their own snapshotted prices
(FR-4.5b), so re-rendering it tomorrow produces the same page it produced
today — which makes a stored blob a cache of something that cannot change,
and a storage decision nobody has to make. What keeps that literally true
byte for byte is ``DocumentPage.start`` pinning the PDF's creation date to
the confirm timestamp (FR-8.3).

**One subtotal per currency, never their sum** (§4.5 rule 4). A sale of a
USD phone and a UZS case prints two figures side by side, and there is no
line on this page where they could be added.
"""

from uuid import UUID

from application.dtos import Letterhead
from domain.entities import SalesInvoice
from domain.value_objects import Money
from infrastructure.documents.page import DocumentPageFactory

_HEADERS = ("Item", "Qty", "Price", "Total")
_WIDTHS = (95.0, 20.0, 30.0, 35.0)


class PdfInvoiceRenderer:
    def __init__(self, pages: DocumentPageFactory) -> None:
        self._pages = pages

    def render(
        self, invoice: SalesInvoice, letterhead: Letterhead, descriptions: dict[UUID, str]
    ) -> bytes:
        page = self._pages.page()
        page.start(invoice)
        page.letterhead(letterhead)
        page.heading(invoice, "Invoice")
        page.table(_HEADERS, _WIDTHS, self._rows(invoice, descriptions))
        page.subtotals(invoice.subtotals())
        page.cancellation(invoice)
        return page.output()

    def _rows(
        self, invoice: SalesInvoice, descriptions: dict[UUID, str]
    ) -> list[tuple[str, str, str, str]]:
        return [
            (
                descriptions.get(line.id, str(line.product_id)),
                str(line.quantity),
                self._amount(line.charged_price),
                self._amount(line.line_total),
            )
            for line in invoice.lines
        ]

    @staticmethod
    def _amount(amount: Money | None) -> str:
        return "" if amount is None else amount.format()
