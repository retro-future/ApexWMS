"""Wire → domain conversion shared by the catalog handlers.

**Prices cross the wire as a string or an int, never a JSON number with a
fraction.** ``"600.50"`` is exact; ``600.50`` is an IEEE double that is
not exactly six hundred and fifty cents. ``Money.from_major`` refuses
floats outright (PRD §4.5), so keeping the annotation to ``str | int`` is
what makes a fractional amount a validation error at the edge instead of
a rounding surprise three layers down.
"""

from domain.value_objects import Currency, Money


class SalePriceParser:
    def parse(self, amount: str | int | None, currency: Currency) -> Money | None:
        """A major-unit amount in *currency*, or None when unpriced."""
        if amount is None:
            return None
        return Money.from_major(amount, currency)
