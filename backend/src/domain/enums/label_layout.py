"""How a product label PDF is laid out for printing.

``SINGLE`` is one 58x40 mm label for a tape printer; ``SHEET`` is an A4
page with a grid of the same label for an ordinary office printer.
"""

from enum import StrEnum


class LabelLayout(StrEnum):
    SINGLE = "single"
    SHEET = "sheet"
