"""The supported currencies and their decimal exponents.

The two supported currencies do NOT share a decimal exponent:

    USD → exponent 2 (cents):   Money(100000, USD) is $1,000.00
    UZS → exponent 0 (whole som): Money(1000, UZS) is 1 000 so'm

ISO 4217 nominally gives UZS exponent 2 (tiyin), but tiyin are defunct;
we deliberately treat UZS as exponent 0 (PRD §4.5). The exponent lives
here, on the currency — call sites may never assume one.
"""

from enum import StrEnum


class Currency(StrEnum):
    UZS = "UZS"
    USD = "USD"

    @property
    def exponent(self) -> int:
        return _EXPONENTS[self]


_EXPONENTS: dict[Currency, int] = {
    Currency.UZS: 0,
    Currency.USD: 2,
}
