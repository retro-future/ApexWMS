"""The bundled Cyrillic font is present and usable.

Without it, Russian document text degrades to '?' (page.py). The file is
checked into the repo so a deployment only has to set APEXWMS_PDF_FONT_PATH.
"""

from pathlib import Path

from fpdf import FPDF

from application.localization.catalog import MessageCatalog
from application.localization.locale import Locale
from infrastructure.documents.page import DocumentPageFactory

_FONT = (
    Path(__file__).parents[2]
    / "src/infrastructure/documents/fonts/DejaVuSans.ttf"
)


def test_bundled_font_exists() -> None:
    assert _FONT.is_file() and _FONT.stat().st_size > 100_000


def test_fpdf_can_render_cyrillic_with_it() -> None:
    pdf = FPDF()
    pdf.add_font("dv", "", str(_FONT))
    pdf.add_page()
    pdf.set_font("dv", size=12)
    pdf.cell(0, 10, "Счёт-фактура")
    assert bytes(pdf.output()).startswith(b"%PDF")


def test_page_keeps_cyrillic_when_a_font_is_configured() -> None:
    page = DocumentPageFactory(MessageCatalog(), str(_FONT)).page(Locale.RU)
    assert page._text("Возврат") == "Возврат"


def test_page_degrades_cyrillic_without_a_font() -> None:
    page = DocumentPageFactory(MessageCatalog()).page(Locale.RU)
    assert page._text("Возврат") == "???????"
