"""The order sent to a supplier (PRD §5.3, FR-3.2, FR-8.1).

The one document type whose page carries costs rather than prices, which is
why its route asks for ``Permission.COST_VIEW`` on top of the order's own
read permission.

There is no IMEI column: a Purchase Order is an intention to buy (§4.4) and
the handsets it describes do not exist yet.
"""

from uuid import UUID

from application.dtos import Letterhead
from application.localization.locale import Locale
from domain.entities import PurchaseOrder
from domain.value_objects import Money
from infrastructure.documents.page import DocumentPage, DocumentPageFactory

_WIDTHS = (95.0, 20.0, 30.0, 35.0)


class PdfPurchaseOrderRenderer:
    def __init__(self, pages: DocumentPageFactory) -> None:
        self._pages = pages

    def render(
        self,
        order: PurchaseOrder,
        letterhead: Letterhead,
        supplier: str | None,
        descriptions: dict[UUID, str],
        locale: Locale,
    ) -> bytes:
        page = self._pages.page(locale)
        page.start(order)
        page.letterhead(letterhead)
        page.heading(order, page.t("purchase_order_title"))
        page.details([(page.t("detail_supplier"), supplier or str(order.supplier_id))])
        page.table(_headers(page), _WIDTHS, self._rows(order, descriptions))
        page.subtotals(order.subtotals())
        page.cancellation(order)
        return page.output()

    def _rows(
        self, order: PurchaseOrder, descriptions: dict[UUID, str]
    ) -> list[tuple[str, str, str, str]]:
        return [
            (
                descriptions.get(line.id, str(line.product_id)),
                str(line.quantity),
                self._amount(line.unit_cost),
                self._amount(line.total_cost),
            )
            for line in order.lines
        ]

    @staticmethod
    def _amount(amount: Money | None) -> str:
        return "" if amount is None else amount.format()


def _headers(page: DocumentPage) -> tuple[str, str, str, str]:
    return (
        page.t("col_item"),
        page.t("col_qty"),
        page.t("col_unit_cost"),
        page.t("col_total"),
    )
