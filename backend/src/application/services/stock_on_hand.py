"""FR-9.1: what the store is holding, grouped and valued per currency.

Two tracking types with different cost rules (§4.6) meet here. Serialized
handsets arrive already grouped and summed; accessories arrive as pairs and
are valued through ``CostPoolReader`` — the same replay ``InvoicePoster``
books COGS from and ``LedgerReconciler`` checks FR-10.7 against, because a
second implementation would let this report disagree with the audit meant
to catch real disagreements.

Both halves fold into a ``CurrencyTotals``, which keys every amount by
its own currency, so no grouping here can put a dollar figure in the som
column. The merge and the paging happen in Python because an aggregate has
to be complete before it can be sliced. Group counts are small; the pool replay
per pair is the real cost, and it is the same one FR-10.7 already pays.
"""

from uuid import UUID

from application.dtos import OnHandBucket, StockGroupBy, StockOnHandGroup
from application.ports import StockOnHandQueries
from application.services.cost_pools import CostPoolReader
from domain.value_objects import CurrencyTotals


class StockOnHandReader:
    def __init__(self, stock: StockOnHandQueries, pools: CostPoolReader) -> None:
        self._stock = stock
        self._pools = pools

    async def read(
        self,
        group_by: StockGroupBy,
        location_id: UUID | None = None,
        product_id: UUID | None = None,
        brand: str | None = None,
    ) -> list[StockOnHandGroup]:
        quantities: dict[UUID | str | None, int] = {}
        labels: dict[UUID | str | None, str] = {}
        skus: dict[UUID | str | None, str | None] = {}
        values: dict[UUID | str | None, CurrencyTotals] = {}

        def fold(bucket: OnHandBucket) -> None:
            labels[bucket.key] = bucket.label
            skus[bucket.key] = bucket.sku
            quantities[bucket.key] = quantities.get(bucket.key, 0) + bucket.quantity
            running = values.get(bucket.key, CurrencyTotals.empty())
            values[bucket.key] = running.add(bucket.value)

        for bucket in await self._stock.serialized_totals(
            group_by, location_id, product_id, brand
        ):
            fold(bucket)

        for row in await self._stock.accessories_on_hand(
            group_by, location_id, product_id, brand
        ):
            pool = await self._pools.pool_for(row.product_id, row.location_id)
            if pool is None:
                continue
            fold(
                OnHandBucket(
                    key=row.key,
                    label=row.label,
                    quantity=row.quantity,
                    value=pool.value,
                    sku=row.sku,
                )
            )

        return [
            StockOnHandGroup(
                group_by=group_by,
                key=key,
                label=labels[key],
                quantity=quantities[key],
                cost_value=values[key],
                sku=skus[key],
            )
            for key in sorted(labels, key=lambda one: (labels[one], str(one)))
        ]
