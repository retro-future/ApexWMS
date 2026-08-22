"""FR-10.7: goods and money must agree, per currency.

The service behind ``apexwms verify-financials``. On-hand inventory value
is recomputed from stock and checked against what the financial ledger
says the store should be holding — one figure per currency, never a sum.
"""

from application.ports import (
    DeviceUnitRepository,
    FinancialTransactionRepository,
    StockMovementRepository,
)
from application.services.cost_pools import INVENTORY_SIGN, CostPoolReader
from application.services.verification.discrepancy import Discrepancy
from domain.value_objects import Currency, Money


class LedgerReconciler:
    """FR-10.7: goods and money must agree, per currency."""

    def __init__(
        self,
        units: DeviceUnitRepository,
        transactions: FinancialTransactionRepository,
        movements: StockMovementRepository,
        pools: CostPoolReader,
    ) -> None:
        self._units = units
        self._transactions = transactions
        self._movements = movements
        self._pools = pools

    async def on_hand_value(self) -> dict[Currency, Money]:
        """What the store is holding, **per currency**, computed from stock.

        Two rules, because the two tracking types genuinely differ (§4.6):
        serialized phones by specific identification — each unit's own
        cost, a fact rather than a model — and quantity accessories by a
        weighted-average pool replayed from the ledger.

        This is the *independent* side of FR-10.7. The quantities come from
        the stock ledger and the purchase costs from the money ledger, so a
        COGS booked at the wrong average shows up here as a disagreement
        with what the money ledger thinks it is holding.
        """
        totals: dict[Currency, Money] = {}
        for unit in await self._units.list_on_hand():
            _accumulate(totals, unit.acquisition_cost)
        for product_id, location_id in await self._movements.list_moved_pairs():
            pool = await self._pools.pool_for(product_id, location_id)
            if pool is not None and not pool.value.is_zero:
                _accumulate(totals, pool.value)
        return totals

    async def ledger_value(self) -> dict[Currency, Money]:
        """What the money ledger says the store should be holding.

        ``purchases − COGS − write-offs − return credits ± adjustments``
        (FR-10.5), computed since inception because the ledger is complete
        and immutable — no stored snapshot is needed for correctness
        (§5.10).

        Revenue is deliberately absent: it is what the goods *sold for*,
        not what they *cost*, and adding it here would compare a selling
        price against an inventory value.
        """
        totals: dict[Currency, Money] = {}
        for (txn_type, _), amount in (await self._transactions.totals_by_type()).items():
            sign = INVENTORY_SIGN.get(txn_type)
            if sign is not None:
                _accumulate(totals, amount * sign)
        return totals

    async def reconcile(self) -> list[Discrepancy]:
        """A mismatch is surfaced, never silently corrected (FR-10.7)."""
        on_hand = await self.on_hand_value()
        ledger = await self.ledger_value()
        found: list[Discrepancy] = []

        for currency in sorted(set(on_hand) | set(ledger), key=lambda c: c.value):
            stock = on_hand.get(currency, Money.zero(currency))
            books = ledger.get(currency, Money.zero(currency))
            if stock != books:
                found.append(
                    Discrepancy(
                        subject=f"inventory value in {currency.value}",
                        expected=books.format(),
                        found=stock.format(),
                    )
                )
        return found


def _accumulate(totals: dict[Currency, Money], amount: Money) -> None:
    """Add *amount* to its own currency's running total, and only its own.

    The one operation every per-currency figure here is built from — so
    there is nowhere a USD amount could land in the UZS column (§4.5
    rule 4). The key is derived from the amount rather than passed in,
    which is what makes that structural.
    """
    running = totals.get(amount.currency)
    totals[amount.currency] = amount if running is None else running + amount
