"""One figure per currency present, never their sum (FR-2.7).

The one calculation all three documents share (``PurchaseOrder``,
``GoodsReceipt``, ``SalesInvoice``): each rolls its own lines up into
subtotals through this, rather than three copies of the same fold.
"""

from collections.abc import Iterable

from domain.value_objects import Currency, Money


class SubtotalsCalculator:
    """Stateless: its one method is a pure function of *amounts*."""

    @staticmethod
    def by_currency(amounts: Iterable[Money | None]) -> dict[Currency, Money]:
        """``None`` is skipped rather than refused: a draft is read while it is
        still being filled in, and a sales invoice draft holds no prices at all.
        """
        totals: dict[Currency, Money] = {}
        for amount in amounts:
            if amount is None:
                continue
            running = totals.get(amount.currency, Money.zero(amount.currency))
            totals[amount.currency] = running + amount
        return totals
