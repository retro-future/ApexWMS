"""IMEI value object — 15 digits with a valid Luhn check digit.

An IMEI that cannot exist in an invalid state deletes an entire class of
bugs: a typo'd IMEI is worse than no IMEI (PRD §4.2). Validation happens
here, in pure Python, with no I/O — uniqueness within the tenant is a
separate, database-level concern.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import InvalidIMEIError

IMEI_LENGTH = 15


def _luhn_checksum(digits: str) -> int:
    total = 0
    # From the rightmost digit: positions 1, 3, 5, ... are taken as-is;
    # positions 2, 4, 6, ... are doubled, with two-digit results summed.
    for offset, ch in enumerate(reversed(digits)):
        d = int(ch)
        if offset % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10


@dataclass(frozen=True, slots=True)
class IMEI:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidIMEIError(f"IMEI must be a string, got {type(self.value).__name__}")
        if len(self.value) != IMEI_LENGTH:
            raise InvalidIMEIError(
                f"IMEI must be exactly {IMEI_LENGTH} digits, got {len(self.value)}"
            )
        if not self.value.isascii() or not self.value.isdigit():
            raise InvalidIMEIError("IMEI must contain only digits 0-9")
        if _luhn_checksum(self.value) != 0:
            raise InvalidIMEIError(f"IMEI {self.value} fails the Luhn check digit")

    @classmethod
    def parse(cls, raw: str) -> IMEI:
        """Parse operator input: tolerate surrounding whitespace and
        common scanner separators (spaces, hyphens) inside the code."""
        cleaned = raw.strip().replace(" ", "").replace("-", "")
        return cls(cleaned)

    def __str__(self) -> str:
        return self.value
