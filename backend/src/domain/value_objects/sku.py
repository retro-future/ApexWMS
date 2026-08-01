"""SKU value object — the catalog's stable, human-typed product code.

A SKU is what a person reads off a shelf label and what FR-7.1 resolves a
scanned string against, so it is normalized *here* rather than at each
call site: ``sku-001``, ``SKU-001 `` and ``Sku-001`` are the same product,
and two of them must not become two rows.

Uniqueness is a database-level concern, deliberately not handled here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from domain.errors import InvalidSkuError


@dataclass(frozen=True, slots=True)
class SKU:
    value: str

    MAX_LENGTH: ClassVar[int] = 64
    _ALLOWED_EXTRA: ClassVar[frozenset[str]] = frozenset("._-/")

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidSkuError(f"SKU must be a string, got {type(self.value).__name__}")
        if not self.value:
            raise InvalidSkuError("SKU must not be empty")
        if len(self.value) > self.MAX_LENGTH:
            raise InvalidSkuError(
                f"SKU must be at most {self.MAX_LENGTH} characters, got {len(self.value)}"
            )
        # Upper-case ASCII only: the normalization in parse() is the single
        # entry point, so anything else here means it was bypassed.
        illegal = [
            ch
            for ch in self.value
            if not (
                ch.isascii() and (ch.isdigit() or ch.isupper() or ch in self._ALLOWED_EXTRA)
            )
        ]
        if illegal:
            raise InvalidSkuError(
                f"SKU may contain only A-Z, 0-9 and {''.join(sorted(self._ALLOWED_EXTRA))}; "
                f"found {''.join(dict.fromkeys(illegal))!r}"
            )

    @classmethod
    def parse(cls, raw: str) -> SKU:
        """Normalize operator input: trim, collapse to upper case."""
        if not isinstance(raw, str):
            raise InvalidSkuError(f"SKU must be a string, got {type(raw).__name__}")
        return cls(raw.strip().upper())

    def __str__(self) -> str:
        return self.value
