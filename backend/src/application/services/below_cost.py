"""Accessories whose weighted-average cost has caught up to their catalog
price (FR-2.19).

Selling below cost is sometimes deliberate (clearance, damage). This never
blocks; it makes the case visible. The pool is replayed from the ledgers
(``CostPoolReader``), not read from a column — there is none.
"""

from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from application.common.repository import TenantDbRepository
from application.dtos import BelowCostAlert
from application.services.cost_pools import CostPoolReader
from domain.entities import GoodsReceipt, Product, SalesInvoice
from infrastructure.persistence.tenant.models import ProductModel


class _CostedLine(Protocol):
    @property
    def product_id(self) -> UUID: ...
    @property
    def is_serial(self) -> bool: ...


class BelowCostChecker:
    def __init__(
        self,
        products: TenantDbRepository[Product, ProductModel],
        pools: CostPoolReader,
    ) -> None:
        self._products = products
        self._pools = pools

    async def alerts_for(self, receipt: GoodsReceipt) -> list[BelowCostAlert]:
        return await self._alerts_for(receipt.lines, receipt.location_id)

    async def alerts_for_invoice(self, invoice: SalesInvoice) -> list[BelowCostAlert]:
        return await self._alerts_for(invoice.lines, invoice.location_id)

    async def _alerts_for(
        self, lines: Iterable[_CostedLine], location_id: UUID
    ) -> list[BelowCostAlert]:
        seen: set[UUID] = set()
        alerts: list[BelowCostAlert] = []
        for line in lines:
            if line.is_serial or line.product_id in seen:
                continue
            seen.add(line.product_id)
            alert = await self._alert_for(line.product_id, location_id)
            if alert is not None:
                alerts.append(alert)
        return alerts

    async def _alert_for(
        self, product_id: UUID, location_id: UUID
    ) -> BelowCostAlert | None:
        product = await self._products.get(product_id)
        if product is None or not product.is_active or product.default_sale_price is None:
            return None
        pool = await self._pools.pool_for(product_id, location_id)
        if pool is None:
            return None
        average = pool.average_unit_cost
        if average is None:
            return None
        # Same exact test as ``SqlBelowCostQueries``' HAVING clause: compare
        # the whole pool value, not the rounded per-unit average, so the two
        # paths cannot disagree in the ``[p*q - q/2, p*q)`` rounding window.
        # ``average`` below is display only.
        price = product.default_sale_price
        if pool.value.amount_minor < price.amount_minor * pool.quantity:
            return None
        return BelowCostAlert(
            product_id=product_id,
            sku=str(product.sku),
            catalog_price=product.default_sale_price,
            average_unit_cost=average,
        )
