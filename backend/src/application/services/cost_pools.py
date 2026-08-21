"""What an accessory costs, replayed from the two ledgers (§4.6).

A serialized phone carries its own ``acquisition_cost``, so its COGS is a
fact. A quantity accessory has no per-unit identity, so its cost is a
weighted-average pool — and that pool is **not a stored column**. It is
rebuilt from the stock ledger's quantities and the money ledger's purchase
values, the same way every other projection here is derived rather than
maintained.

One replay, two callers, and that is the point: ``InvoicePoster`` books
COGS from it at confirm, and ``LedgerReconciler`` recomputes on-hand value
from it for FR-10.7. If these were separate implementations, a sale booked
at one average and reconciled against another would show up as a
discrepancy in the check that exists to catch real ones.
"""

from uuid import UUID

from application.ports import (
    FinancialTransactionRepository,
    ProductRepository,
    StockMovementRepository,
)
from domain.enums import TransactionType
from domain.value_objects import CostPool, Money

# How each category moves *inventory value*, which is not the same as how
# it moves money — and the mismatch is the trap this table exists to close.
#
# §4.6's signs describe cash: a ``PURCHASE`` is stored negative because
# money left the till, while the goods it bought made the shelves *worth
# more*. A ``SUPPLIER_RETURN_CREDIT`` is stored positive for the same
# reason in reverse. So two categories have to be flipped to read as
# inventory, and ``COUNT_ADJUSTMENT`` — whose sign already describes goods
# found or missing — does not.
INVENTORY_SIGN: dict[TransactionType, int] = {
    TransactionType.PURCHASE: -1,
    TransactionType.COGS: +1,
    TransactionType.WRITE_OFF_LOSS: +1,
    TransactionType.SUPPLIER_RETURN_CREDIT: -1,
    TransactionType.COUNT_ADJUSTMENT: +1,
}
# SALE_REVENUE and PAYMENT_RECEIVED are absent, not zero: they are figures
# about the customer, and no sign would make them belong here.


class CostPoolReader:
    """Rebuilds one accessory's weighted-average pool at a location."""

    def __init__(
        self,
        products: ProductRepository,
        movements: StockMovementRepository,
        transactions: FinancialTransactionRepository,
    ) -> None:
        self._products = products
        self._movements = movements
        self._transactions = transactions

    async def pool_for(self, product_id: UUID, location_id: UUID) -> CostPool | None:
        """Replay the pool from the two ledgers, or None if the product is gone.

        Receipts take their value from the ``PURCHASE`` (or surplus
        ``COUNT_ADJUSTMENT``) entry the same document wrote, in **total**
        rather than per unit — dividing a line's cost out and multiplying
        it back would introduce a rounding error that was never in the
        data. Issues take their proportional share (``CostPool.issue``),
        which is what makes a sold-out pool land on exactly zero.
        """
        product = await self._products.get(product_id)
        if product is None:
            return None

        value_in = await self._value_added_per_document(product_id, location_id)
        pool = CostPool.empty(product.currency)
        for movement in await self._movements.list_for_pair(product_id, location_id):
            if movement.quantity_delta > 0:
                pool = pool.receive_total(
                    movement.quantity_delta,
                    value_in.pop(movement.document_id, Money.zero(product.currency)),
                )
            else:
                pool, _ = pool.issue(-movement.quantity_delta)
        return pool

    async def _value_added_per_document(
        self, product_id: UUID, location_id: UUID
    ) -> dict[UUID, Money]:
        """How much each document added to this pool's value.

        Only the inbound categories: an issue's cost is *computed* from the
        pool, never read back out of the ledger, or the check would be
        comparing the money ledger against itself.
        """
        added: dict[UUID, Money] = {}
        for txn in await self._transactions.list_for_pair(product_id, location_id):
            sign = INVENTORY_SIGN.get(txn.txn_type)
            if sign is None:
                continue
            contribution = txn.amount * sign
            if contribution.is_negative or contribution.is_zero:
                continue
            running = added.get(txn.document_id)
            added[txn.document_id] = contribution if running is None else running + contribution
        return added
