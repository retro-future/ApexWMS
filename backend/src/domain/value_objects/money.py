"""Money value object — UZS and USD, integer minor units, per-currency exponents.

The two supported currencies do NOT share a decimal exponent:

    USD → exponent 2 (cents):   Money(100000, USD) is $1,000.00
    UZS → exponent 0 (whole som): Money(1000, UZS) is 1 000 so'm

ISO 4217 nominally gives UZS exponent 2 (tiyin), but tiyin are defunct;
we deliberately treat UZS as exponent 0 (PRD §4.5). The exponent lives
here, on the value object — call sites may never assume one.

A bare integer is not money. Floats are never money.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Self

from domain.errors import CurrencyMismatchError, InvalidMoneyError


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


@dataclass(frozen=True, slots=True)
class Money:
    """An exact amount in a currency's minor unit. Immutable.

    Arithmetic and comparison are only defined between Money of the SAME
    currency; anything else raises CurrencyMismatchError. There is no
    implicit conversion anywhere in the domain (FR-2.10).
    """

    amount_minor: int
    currency: Currency

    def __post_init__(self) -> None:
        # bool is an int subclass; it is not money either.
        if not isinstance(self.amount_minor, int) or isinstance(self.amount_minor, bool):
            raise InvalidMoneyError(
                f"amount_minor must be an int, got {type(self.amount_minor).__name__}"
            )
        if not isinstance(self.currency, Currency):
            raise InvalidMoneyError(f"currency must be a Currency, got {self.currency!r}")

    # --- construction -------------------------------------------------

    @classmethod
    def zero(cls, currency: Currency) -> Self:
        return cls(0, currency)

    @classmethod
    def from_major(cls, amount: int | str | Decimal, currency: Currency) -> Self:
        """Build from a major-unit amount ("10.50" USD → 1050 cents).

        Accepts int, str, or Decimal — never float: binary floats cannot
        represent decimal money exactly, and a lost fraction in an
        inventory system is indistinguishable from theft.
        Raises if the amount has more precision than the currency allows.
        """
        if isinstance(amount, float):
            raise InvalidMoneyError("float is not money; pass int, str, or Decimal")
        try:
            dec = Decimal(amount)
        except InvalidOperation as exc:
            raise InvalidMoneyError(f"not a valid amount: {amount!r}") from exc
        scaled = dec.scaleb(currency.exponent)
        if scaled != scaled.to_integral_value():
            raise InvalidMoneyError(
                f"{amount} has more precision than {currency.value} allows "
                f"(exponent {currency.exponent})"
            )
        return cls(int(scaled), currency)

    # --- arithmetic (same-currency only) ------------------------------

    def _require_same_currency(self, other: object) -> Money:
        if not isinstance(other, Money):
            raise CurrencyMismatchError(f"cannot combine Money with {type(other).__name__}")
        if other.currency is not self.currency:
            raise CurrencyMismatchError(
                f"cannot combine {self.currency.value} with {other.currency.value}"
            )
        return other

    def __add__(self, other: Money) -> Money:
        other = self._require_same_currency(other)
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __sub__(self, other: Money) -> Money:
        other = self._require_same_currency(other)
        return Money(self.amount_minor - other.amount_minor, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount_minor, self.currency)

    def __mul__(self, factor: int) -> Money:
        if not isinstance(factor, int) or isinstance(factor, bool):
            raise InvalidMoneyError("Money can only be multiplied by an int")
        return Money(self.amount_minor * factor, self.currency)

    __rmul__ = __mul__

    def __lt__(self, other: Money) -> bool:
        return self.amount_minor < self._require_same_currency(other).amount_minor

    def __le__(self, other: Money) -> bool:
        return self.amount_minor <= self._require_same_currency(other).amount_minor

    def __gt__(self, other: Money) -> bool:
        return self.amount_minor > self._require_same_currency(other).amount_minor

    def __ge__(self, other: Money) -> bool:
        return self.amount_minor >= self._require_same_currency(other).amount_minor

    # --- predicates ----------------------------------------------------

    @property
    def is_zero(self) -> bool:
        return self.amount_minor == 0

    @property
    def is_negative(self) -> bool:
        return self.amount_minor < 0

    # --- presentation ---------------------------------------------------

    def as_major(self) -> Decimal:
        """The amount in major units, as an exact Decimal."""
        return Decimal(self.amount_minor).scaleb(-self.currency.exponent)

    def format(self) -> str:
        """Human-readable rendering (FR-2.9).

        Money(1000, UZS) → "1 000 so'm"
        Money(1000, USD) → "$10.00"
        """
        sign = "-" if self.amount_minor < 0 else ""
        magnitude = abs(self.amount_minor)
        if self.currency is Currency.USD:
            dollars, cents = divmod(magnitude, 100)
            return f"{sign}${dollars:,}.{cents:02d}"
        som = f"{magnitude:,}".replace(",", " ")
        return f"{sign}{som} so'm"

    def __str__(self) -> str:
        return self.format()
