"""The invoice, on paper (PRD §5.8, FR-8.1, FR-4.6).

Rendered on demand rather than stored at confirm. A confirmed document is
immutable (§4.4) and its lines carry their own snapshotted prices
(FR-4.5b), so re-rendering it tomorrow produces the same page it produced
today — which makes a stored blob a cache of something that cannot change,
and a storage decision nobody has to make.

**One subtotal per currency, never their sum** (§4.5 rule 4). A sale of a
USD phone and a UZS case prints two figures side by side, and there is no
line on this page where they could be added.

fpdf2's built-in Helvetica covers Latin-1, which is enough for Uzbek Latin
and ``so'm`` but not for Cyrillic. ``APEXWMS_PDF_FONT_PATH`` points at a
Unicode TTF when a store needs Russian names to print properly; without
one, an unencodable character degrades to ``?`` rather than failing the
download, because a Seller trying to print a receipt should get a slightly
wrong receipt rather than a 500.
"""

from pathlib import Path
from uuid import UUID

from fpdf import FPDF

from application.dtos import Letterhead
from domain.entities import SalesInvoice
from domain.value_objects import Currency, Money

_UNICODE_FAMILY = "apex"
_CORE_FAMILY = "Helvetica"
_MARGIN = 15.0
_LINE = 6.0


class PdfInvoiceRenderer:
    def __init__(self, font_path: str | None = None) -> None:
        path = Path(font_path) if font_path else None
        self._font_path = path if path is not None and path.is_file() else None

    def render(
        self, invoice: SalesInvoice, letterhead: Letterhead, descriptions: dict[UUID, str]
    ) -> bytes:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=_MARGIN)
        pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)
        pdf.add_page()
        family = self._register_font(pdf)

        self._letterhead(pdf, family, letterhead)
        self._heading(pdf, family, invoice)
        self._lines(pdf, family, invoice, descriptions)
        self._subtotals(pdf, family, invoice)
        self._cancellation(pdf, family, invoice)

        return bytes(pdf.output())

    def _register_font(self, pdf: FPDF) -> str:
        """The Unicode face if the deployment supplied one, else the core."""
        if self._font_path is None:
            return _CORE_FAMILY
        pdf.add_font(_UNICODE_FAMILY, "", str(self._font_path))
        return _UNICODE_FAMILY

    def _letterhead(self, pdf: FPDF, family: str, letterhead: Letterhead) -> None:
        if letterhead.business_name:
            pdf.set_font(family, size=16)
            pdf.cell(
                0,
                _LINE * 1.5,
                self._text(letterhead.business_name),
                new_x="LMARGIN",
                new_y="NEXT",
            )
        if letterhead.address:
            pdf.set_font(family, size=9)
            pdf.multi_cell(0, _LINE * 0.8, self._text(letterhead.address))
        pdf.ln(_LINE * 0.5)

    def _heading(self, pdf: FPDF, family: str, invoice: SalesInvoice) -> None:
        pdf.set_font(family, size=13)
        pdf.cell(0, _LINE * 1.4, self._text(invoice.number), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(family, size=9)
        confirmed = invoice.confirmed_at
        if confirmed is not None:
            pdf.cell(
                0,
                _LINE,
                self._text(f"Confirmed {confirmed:%Y-%m-%d %H:%M %Z}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )
        pdf.ln(_LINE * 0.5)

    def _lines(
        self, pdf: FPDF, family: str, invoice: SalesInvoice, descriptions: dict[UUID, str]
    ) -> None:
        widths = (95.0, 20.0, 30.0, 35.0)
        pdf.set_font(family, size=9)
        for label, width in zip(("Item", "Qty", "Price", "Total"), widths, strict=True):
            pdf.cell(width, _LINE, self._text(label), border="B")
        pdf.ln(_LINE)

        for line in invoice.lines:
            total = line.line_total
            cells = (
                descriptions.get(line.id, str(line.product_id)),
                str(line.quantity),
                self._amount(line.charged_price),
                self._amount(total),
            )
            for value, width in zip(cells, widths, strict=True):
                pdf.cell(width, _LINE, self._text(value))
            pdf.ln(_LINE)

    def _subtotals(self, pdf: FPDF, family: str, invoice: SalesInvoice) -> None:
        pdf.ln(_LINE * 0.5)
        pdf.set_font(family, size=11)
        # One row per currency present. There is deliberately no combined
        # figure anywhere on this page (FR-2.7).
        for currency, amount in sorted(
            invoice.subtotals().items(), key=lambda pair: pair[0].value
        ):
            pdf.cell(115.0, _LINE, "")
            pdf.cell(
                65.0,
                _LINE,
                self._text(f"{self._currency_label(currency)}  {amount.format()}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )

    def _cancellation(self, pdf: FPDF, family: str, invoice: SalesInvoice) -> None:
        """A cancelled sale still prints, and says so (§4.3 rule 2)."""
        if invoice.cancelled_at is None:
            return
        pdf.ln(_LINE)
        pdf.set_font(family, size=10)
        reason = invoice.cancellation_reason or "no reason given"
        pdf.multi_cell(0, _LINE, self._text(f"CANCELLED: {reason}"))

    @staticmethod
    def _currency_label(currency: Currency) -> str:
        return f"Total ({currency.value})"

    @staticmethod
    def _amount(amount: Money | None) -> str:
        return "" if amount is None else amount.format()

    def _text(self, value: str) -> str:
        """Latin-1 fallback: a name the core font cannot draw becomes '?'.

        Only ever lossy on the built-in font; with a Unicode face
        registered, fpdf2 encodes the string as it stands.
        """
        if self._font_path is not None:
            return value
        return value.encode("latin-1", "replace").decode("latin-1")
