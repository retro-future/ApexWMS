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

from application.common.repository import TenantAppendOnlyRepository, TenantDbRepository
from application.errors import NotFoundError
from application.specs import MovementsForPair, TransactionsForPair
from domain.entities import FinancialTransaction, Product, StockMovement
from domain.enums import TransactionType
from domain.value_objects import CostPool, Money
from infrastructure.persistence.tenant.models import (
    FinancialTransactionModel,
    ProductModel,
    StockMovementModel,
)

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
        products: TenantDbRepository[Product, ProductModel],
        movements: TenantAppendOnlyRepository[StockMovement, StockMovementModel],
        transactions: TenantAppendOnlyRepository[
            FinancialTransaction, FinancialTransactionModel
        ],
    ) -> None:
        self._products = products
        self._movements = movements
        self._transactions = transactions

    async def issue_value(
        self, product_id: UUID, location_id: UUID, quantity: int
    ) -> Money:
        """What *quantity* of this accessory is carried at (§4.6).

        The figure every document that takes accessories off a shelf books:
        COGS on a sale, the credit on a supplier return, the loss on a
        write-off, the shortage on a count. One implementation, so four
        documents cannot disagree about what the same goods were worth —
        the same reason ``pool_for`` has one caller in each direction rather
        than a copy per use.
        """
        pool = await self.pool_for(product_id, location_id)
        if pool is None:
            raise NotFoundError(f"product {product_id} does not exist in this store")
        _, value = pool.issue(quantity)
        return value

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
        for movement in await self._movements.find(
            MovementsForPair(product_id, location_id)
        ):
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
        for txn in await self._transactions.find(
            TransactionsForPair(product_id, location_id)
        ):
            sign = INVENTORY_SIGN.get(txn.txn_type)
            if sign is None:
                continue
            contribution = txn.amount * sign
            if contribution.is_negative or contribution.is_zero:
                continue
            running = added.get(txn.document_id)
            added[txn.document_id] = contribution if running is None else running + contribution
        return added
