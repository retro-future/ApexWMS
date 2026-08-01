"""Barcode value object — EAN/UPC with a valid GS1 check digit.

Same reasoning as ``imei.py``: a barcode that cannot exist in an invalid
state deletes a class of bugs, and a mis-scanned barcode is worse than no
barcode. The GS1 mod-10 check digit catches exactly the single-digit and
most transposition errors a scanner or a typist produces.

Four lengths are accepted, covering everything a phone shop meets:
EAN-8, UPC-A (12), EAN-13, and ITF-14 (a carton of chargers).

Uniqueness is a database-level concern, deliberately not handled here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from domain.errors import InvalidBarcodeError


def _gs1_check_digit(digits: str) -> int:
    """The GS1 mod-10 check digit for *digits* (payload, without it).

    Weights alternate 3 and 1 from the right of the payload, so the
    rightmost payload digit always carries weight 3.
    """
    total = sum(
        int(ch) * (3 if offset % 2 == 0 else 1)
        for offset, ch in enumerate(reversed(digits))
    )
    return (10 - total % 10) % 10


@dataclass(frozen=True, slots=True)
class Barcode:
    value: str

    VALID_LENGTHS: ClassVar[tuple[int, ...]] = (8, 12, 13, 14)

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidBarcodeError(
                f"barcode must be a string, got {type(self.value).__name__}"
            )
        if len(self.value) not in self.VALID_LENGTHS:
            raise InvalidBarcodeError(
                f"barcode must be {', '.join(map(str, self.VALID_LENGTHS))} digits (EAN/UPC), "
                f"got {len(self.value)}"
            )
        if not self.value.isascii() or not self.value.isdigit():
            raise InvalidBarcodeError("barcode must contain only digits 0-9")
        if _gs1_check_digit(self.value[:-1]) != int(self.value[-1]):
            raise InvalidBarcodeError(f"barcode {self.value} fails the GS1 check digit")

    @classmethod
    def parse(cls, raw: str) -> Barcode:
        """Parse operator input: tolerate surrounding whitespace and
        common scanner separators (spaces, hyphens) inside the code."""
        if not isinstance(raw, str):
            raise InvalidBarcodeError(f"barcode must be a string, got {type(raw).__name__}")
        return cls(raw.strip().replace(" ", "").replace("-", ""))

    def __str__(self) -> str:
        return self.value
