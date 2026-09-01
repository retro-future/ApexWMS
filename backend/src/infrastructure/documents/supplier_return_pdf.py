"""The note that travels with goods going back (PRD §5.5, FR-5.3, FR-8.1).

**No money on the page and no subtotal block.** What a return is worth is
the goods' book value, which is a ``SUPPLIER_RETURN_CREDIT`` row in the
financial ledger — printing a second opinion about it here is exactly what
``application/models/supplier_return.py`` declines to do for the same
reason. This is a delivery note, not a credit note.

The IMEI comes straight off the line: ``RemovalLine.imei`` is carried by
the repository's join, so nothing here needs the live handset.
"""

from uuid import UUID

from application.dtos import Letterhead
from application.localization.locale import Locale
from domain.entities import SupplierReturn
from infrastructure.documents.page import DocumentPageFactory

_WIDTHS = (95.0, 60.0, 25.0)


class PdfSupplierReturnRenderer:
    def __init__(self, pages: DocumentPageFactory) -> None:
        self._pages = pages

    def render(
        self,
        document: SupplierReturn,
        letterhead: Letterhead,
        supplier: str | None,
        location: str | None,
        descriptions: dict[UUID, str],
        locale: Locale,
    ) -> bytes:
        page = self._pages.page(locale)
        page.start(document)
        page.letterhead(letterhead)
        page.heading(document, page.t("supplier_return_title"))
        page.details(
            [
                (page.t("detail_supplier"), supplier or str(document.supplier_id)),
                (page.t("detail_from"), location or str(document.location_id)),
                (page.t("detail_reason"), document.reason.value.replace("_", " ")),
            ]
        )
        headers = (page.t("col_item"), page.t("col_imei"), page.t("col_qty"))
        page.table(headers, _WIDTHS, self._rows(document, descriptions))
        page.cancellation(document)
        return page.output()

    @staticmethod
    def _rows(
        document: SupplierReturn, descriptions: dict[UUID, str]
    ) -> list[tuple[str, str, str]]:
        return [
            (
                descriptions.get(line.id, str(line.product_id)),
                line.imei or "",
                str(line.quantity),
            )
            for line in document.lines
        ]
