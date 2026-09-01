"""Product shelf labels as a PDF (see ``application/ports/documents.py``).

``python-barcode`` gives the bar/space module string; every bar is a
filled ``fpdf2`` rectangle and all text is drawn with the page font, so
the label needs no raster image and no system libraries.
"""

from pathlib import Path

import barcode
from fpdf import FPDF

from application.dtos import Letterhead, ProductLabel
from domain.enums import LabelLayout

_UNICODE_FAMILY = "apex"
_CORE_FAMILY = "Helvetica"

_SINGLE = (58.0, 40.0)
_A4 = (210.0, 297.0)
_SHEET_COLS = 3
_SHEET_ROWS = 8
_QUIET_MODULES = 10


class PdfLabelRenderer:
    def __init__(self, font_path: str | None = None) -> None:
        path = Path(font_path) if font_path else None
        self._font_path = path if path is not None and path.is_file() else None

    def render(
        self,
        label: ProductLabel,
        letterhead: Letterhead,
        layout: LabelLayout,
        copies: int,
    ) -> bytes:
        store = letterhead.business_name or ""
        if layout is LabelLayout.SINGLE:
            pdf = FPDF(unit="mm", format=_SINGLE)
            pdf.set_auto_page_break(auto=False)
            pdf.set_margins(0, 0, 0)
            pdf.add_page()
            family = self._register_font(pdf)
            self._draw(pdf, family, 0, 0, *_SINGLE, label, store)
            return bytes(pdf.output())

        pdf = FPDF(unit="mm", format=_A4)
        pdf.set_auto_page_break(auto=False)
        pdf.set_margins(0, 0, 0)
        pdf.add_page()
        family = self._register_font(pdf)
        cell_w = _A4[0] / _SHEET_COLS
        cell_h = _A4[1] / _SHEET_ROWS
        for i in range(min(copies, _SHEET_COLS * _SHEET_ROWS)):
            col, row = i % _SHEET_COLS, i // _SHEET_COLS
            self._draw(
                pdf, family, col * cell_w, row * cell_h, cell_w, cell_h, label, store
            )
        return bytes(pdf.output())

    def _draw(
        self,
        pdf: FPDF,
        family: str,
        x: float,
        y: float,
        w: float,
        h: float,
        label: ProductLabel,
        store: str,
    ) -> None:
        pad = 3.0
        inner = w - 2 * pad
        pdf.set_xy(x + pad, y + pad)
        if store:
            pdf.set_font(family, size=7)
            pdf.cell(inner, 3.5, self._text(pdf, store), new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(x + pad)
        pdf.set_font(family, size=9)
        pdf.multi_cell(inner, 4.0, self._text(pdf, label.product_name))
        pdf.set_x(x + pad)

        modules = self._modules(label)
        bar_h = 9.0
        # Follow the text with a small gap; fall back to a bottom anchor only
        # when a long name would otherwise push the bars off the label.
        bar_y = min(pdf.get_y() + 2.0, y + h - pad - bar_h - 3.5)
        unit = inner / (len(modules) + 2 * _QUIET_MODULES)
        cursor = x + pad + _QUIET_MODULES * unit
        pdf.set_fill_color(0, 0, 0)
        for is_bar, run in _runs(modules):
            if is_bar:
                pdf.rect(cursor, bar_y, unit * run, bar_h, style="F")
            cursor += unit * run

        pdf.set_font(family, size=7)
        pdf.set_xy(x + pad, bar_y + bar_h + 0.5)
        pdf.cell(inner, 3.0, label.code_value, align="C")

    @staticmethod
    def _modules(label: ProductLabel) -> str:
        cls = barcode.get_barcode_class("ean13" if label.code_symbology == "ean13" else "code128")
        return cls(label.code_value).build()[0]

    def _register_font(self, pdf: FPDF) -> str:
        if self._font_path is None:
            return _CORE_FAMILY
        pdf.add_font(_UNICODE_FAMILY, "", str(self._font_path))
        return _UNICODE_FAMILY

    def _text(self, pdf: FPDF, value: str) -> str:
        if self._font_path is not None:
            return value
        return value.encode("latin-1", "replace").decode("latin-1")


def _runs(modules: str) -> list[tuple[bool, int]]:
    runs: list[tuple[bool, int]] = []
    for ch in modules:
        is_bar = ch == "1"
        if runs and runs[-1][0] == is_bar:
            runs[-1] = (is_bar, runs[-1][1] + 1)
        else:
            runs.append((is_bar, 1))
    return runs
