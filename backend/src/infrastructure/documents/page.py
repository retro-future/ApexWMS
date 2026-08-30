"""The parts of a printed document that do not vary by document (PRD §5.8).

Composed by each renderer rather than inherited from, so a renderer's
``render`` reads as the list of sections that document actually has — a
Supplier Return note has no subtotal block at all, and inheritance would
have to say so by omission.

**The creation date is pinned to the document's own confirm timestamp**,
because fpdf2 otherwise stamps the wall clock into the PDF and FR-8.3 wants
a regeneration to be byte-identical. A cancelled document keeps using the
confirm time, so adding the CANCELLED mark does not move the date either.

fpdf2's built-in Helvetica covers Latin-1, which is enough for Uzbek Latin
and ``so'm`` but not for Cyrillic. ``APEXWMS_PDF_FONT_PATH`` points at a
Unicode TTF when a store needs Russian names to print properly; without
one, an unencodable character degrades to ``?`` rather than failing the
download, because whoever is printing a receipt should get a slightly wrong
receipt rather than a 500.
"""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from fpdf import FPDF

from application.dtos import Letterhead
from domain.entities import Document
from domain.value_objects import Currency, Money

_UNICODE_FAMILY = "apex"
_CORE_FAMILY = "Helvetica"
_MARGIN = 15.0
_LINE = 6.0
_LOGO_WIDTH = 28.0
# What fpdf2 falls back to when a document was never confirmed. Nothing
# reaches here today (a draft is refused before it renders), but a fixed
# date keeps the renderer a pure function of its inputs regardless.
_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)


class DocumentPage:
    def __init__(self, font: Path | None = None) -> None:
        self._font_path = font
        self._pdf = FPDF()
        self._family = _CORE_FAMILY

    def start(self, document: Document) -> None:
        """One page per render — a ``DocumentPage`` is not reused."""
        self.start_at(document.confirmed_at or _EPOCH)

    def start_at(self, created_at: datetime) -> None:
        """For a page whose subject is not a ``Document`` — the month-end
        report, which is pinned to its period's end (FR-10.10)."""
        self._pdf.set_creation_date(created_at)
        self._pdf.set_auto_page_break(auto=True, margin=_MARGIN)
        self._pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)
        self._pdf.add_page()
        self._family = self._register_font()

    def letterhead(self, letterhead: Letterhead) -> None:
        if letterhead.logo is not None:
            self._pdf.image(BytesIO(letterhead.logo.content), w=_LOGO_WIDTH)
            self._pdf.ln(_LINE * 0.4)
        if letterhead.business_name:
            self._pdf.set_font(self._family, size=16)
            self._cell(0, _LINE * 1.5, letterhead.business_name, wrap=True)
        if letterhead.address:
            self._pdf.set_font(self._family, size=9)
            self._pdf.multi_cell(0, _LINE * 0.8, self._text(letterhead.address))
        self._pdf.ln(_LINE * 0.5)

    def title(self, text: str, subtitle: str = "") -> None:
        """``heading`` for a page with no document number to print."""
        self._pdf.set_font(self._family, size=13)
        self._cell(0, _LINE * 1.4, text, wrap=True)
        if subtitle:
            self._pdf.set_font(self._family, size=9)
            self._cell(0, _LINE, subtitle, wrap=True)
        self._pdf.ln(_LINE * 0.5)

    def heading(self, document: Document, title: str) -> None:
        self._pdf.set_font(self._family, size=13)
        self._cell(0, _LINE * 1.4, f"{title}  {document.number}", wrap=True)
        self._pdf.set_font(self._family, size=9)
        if document.confirmed_at is not None:
            self._cell(
                0, _LINE, f"Confirmed {document.confirmed_at:%Y-%m-%d %H:%M %Z}", wrap=True
            )
        self._pdf.ln(_LINE * 0.5)

    def details(self, rows: Iterable[tuple[str, str]]) -> None:
        """Label/value pairs above the lines — a supplier, a location, a reason."""
        self._pdf.set_font(self._family, size=9)
        for label, value in rows:
            self._pdf.cell(30.0, _LINE, self._text(label))
            self._cell(0, _LINE, value, wrap=True)
        self._pdf.ln(_LINE * 0.5)

    def table(
        self,
        headers: Sequence[str],
        widths: Sequence[float],
        rows: Iterable[Sequence[str]],
    ) -> None:
        self._pdf.set_font(self._family, size=9)
        for label, width in zip(headers, widths, strict=True):
            self._pdf.cell(width, _LINE, self._text(label), border="B")
        self._pdf.ln(_LINE)
        for row in rows:
            for value, width in zip(row, widths, strict=True):
                self._pdf.cell(width, _LINE, self._text(value))
            self._pdf.ln(_LINE)

    def subtotals(self, totals: dict[Currency, Money]) -> None:
        """One row per currency present, never their sum (§4.5 rule 4)."""
        self._pdf.ln(_LINE * 0.5)
        self._pdf.set_font(self._family, size=11)
        for currency, amount in sorted(totals.items(), key=lambda pair: pair[0].value):
            self._pdf.cell(115.0, _LINE, "")
            self._cell(65.0, _LINE, f"Total ({currency.value})  {amount.format()}", wrap=True)

    def cancellation(self, document: Document) -> None:
        """A cancelled document still prints, and says so (§4.3 rule 2)."""
        if document.cancelled_at is None:
            return
        self._pdf.ln(_LINE)
        self._pdf.set_font(self._family, size=10)
        reason = document.cancellation_reason or "no reason given"
        self._pdf.multi_cell(0, _LINE, self._text(f"CANCELLED: {reason}"))

    def output(self) -> bytes:
        return bytes(self._pdf.output())

    def _cell(self, width: float, height: float, value: str, *, wrap: bool) -> None:
        new_x, new_y = ("LMARGIN", "NEXT") if wrap else ("RIGHT", "TOP")
        self._pdf.cell(width, height, self._text(value), new_x=new_x, new_y=new_y)

    def _register_font(self) -> str:
        """The Unicode face if the deployment supplied one, else the core."""
        if self._font_path is None:
            return _CORE_FAMILY
        self._pdf.add_font(_UNICODE_FAMILY, "", str(self._font_path))
        return _UNICODE_FAMILY

    def _text(self, value: str) -> str:
        """Latin-1 fallback: a name the core font cannot draw becomes '?'.

        Only ever lossy on the built-in font; with a Unicode face
        registered, fpdf2 encodes the string as it stands.
        """
        if self._font_path is not None:
            return value
        return value.encode("latin-1", "replace").decode("latin-1")


class DocumentPageFactory:
    """Resolves the font once per process; hands out one page per render.

    A ``DocumentPage`` wraps a mutable ``FPDF``, so it cannot be shared the
    way the renderers are — but deciding whether the configured font file
    exists touches the filesystem, and that belongs at startup.
    """

    def __init__(self, font_path: str | None = None) -> None:
        path = Path(font_path) if font_path else None
        self._font = path if path is not None and path.is_file() else None

    def page(self) -> DocumentPage:
        return DocumentPage(self._font)
