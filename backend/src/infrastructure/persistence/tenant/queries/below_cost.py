"""Accessories at or above their catalog price (see the below-cost design doc).

The average unit cost is rebuilt in SQL, not via ``CostPoolReader``: a store
has hundreds of accessories across locations, and replaying every pool per
request is too much. Pool value for a (product, location) pair equals
``sum(amount_minor * INVENTORY_SIGN[txn_type])`` over the money ledger —
identical to the fold in ``application/services/cost_pools.py``. Keep the
CASE below in step with that table.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Numeric, Row, Select, and_, case, cast, func, select

from application.dtos import BelowCostRow
from application.sorting import BelowCostSort
from domain.enums import TrackingType, TransactionType
from domain.value_objects import Currency, Money
from domain.value_objects.cost_pool import _round_half_up
from infrastructure.persistence.tenant.models import (
    FinancialTransactionModel,
    LocationModel,
    ProductModel,
    StockLevelModel,
)
from infrastructure.types import TenantSession


class SqlBelowCostQueries:
    def __init__(self, session: TenantSession) -> None:
        self._session = session

    async def list_below_cost(
        self,
        page: int,
        page_size: int,
        location_id: UUID | None = None,
        sort: BelowCostSort = BelowCostSort.SHORTFALL,
    ) -> tuple[list[BelowCostRow], int]:
        value_minor = self._pool_value().label("value_minor")
        price_x_qty = (
            ProductModel.default_sale_price_minor * StockLevelModel.quantity
        )
        stmt = (
            select(
                ProductModel.id,
                ProductModel.sku,
                ProductModel.name,
                ProductModel.currency,
                ProductModel.default_sale_price_minor,
                StockLevelModel.location_id,
                LocationModel.name,
                StockLevelModel.quantity,
                value_minor,
            )
            .join(ProductModel, ProductModel.id == StockLevelModel.product_id)
            .join(LocationModel, LocationModel.id == StockLevelModel.location_id)
            .outerjoin(
                FinancialTransactionModel,
                and_(
                    FinancialTransactionModel.product_id == StockLevelModel.product_id,
                    FinancialTransactionModel.location_id == StockLevelModel.location_id,
                    FinancialTransactionModel.device_unit_id.is_(None),
                ),
            )
            .where(
                ProductModel.tracking_type == TrackingType.QUANTITY.value,
                ProductModel.is_active.is_(True),
                ProductModel.default_sale_price_minor.is_not(None),
                StockLevelModel.quantity > 0,
            )
            .group_by(
                ProductModel.id,
                ProductModel.sku,
                ProductModel.name,
                ProductModel.currency,
                ProductModel.default_sale_price_minor,
                StockLevelModel.location_id,
                LocationModel.name,
                StockLevelModel.quantity,
            )
            # average >= price  <=>  value >= price * quantity  (quantity > 0),
            # exact, no rounding.
            .having(value_minor >= price_x_qty)
        )
        if location_id is not None:
            stmt = stmt.where(StockLevelModel.location_id == location_id)

        ordered = self._ordered(stmt, sort, value_minor)
        rows = list(
            await self._session.execute(
                ordered.limit(page_size).offset((page - 1) * page_size)
            )
        )
        total = await self._count(stmt)
        return [self._to_row(row) for row in rows], total

    @staticmethod
    def _pool_value() -> ColumnElement[Any]:
        """``sum(amount_minor * INVENTORY_SIGN[txn_type])`` — the same fold as
        ``application/services/cost_pools.py``'s ``INVENTORY_SIGN``. ``amount_minor``
        is signed by §4.6's cash direction; the two categories whose cash sign is
        opposite their effect on shelf value are flipped here."""
        amount = FinancialTransactionModel.amount_minor
        txn_type = FinancialTransactionModel.txn_type
        return func.sum(
            case(
                (txn_type == TransactionType.PURCHASE.value, -amount),
                (txn_type == TransactionType.COGS.value, amount),
                (txn_type == TransactionType.WRITE_OFF_LOSS.value, amount),
                (txn_type == TransactionType.SUPPLIER_RETURN_CREDIT.value, -amount),
                (txn_type == TransactionType.COUNT_ADJUSTMENT.value, amount),
                else_=0,
            )
        )

    @staticmethod
    def _ordered(
        stmt: Select[Any],
        sort: BelowCostSort,
        value_minor: ColumnElement[Any],
    ) -> Select[Any]:
        if sort is BelowCostSort.SKU:
            return stmt.order_by(ProductModel.sku)
        # Per-unit shortfall, matching ``BelowCostRow.shortfall``: order by
        # ``avg - price``, not the quantity-scaled total. Numeric cast avoids
        # an integer-floor divide.
        return stmt.order_by(
            (
                cast(value_minor, Numeric) / StockLevelModel.quantity
                - ProductModel.default_sale_price_minor
            ).desc()
        )

    async def _count(self, stmt: Select[Any]) -> int:
        subq = stmt.order_by(None).subquery()
        total = await self._session.scalar(
            select(func.count()).select_from(subq)
        )
        return int(total or 0)

    @staticmethod
    def _to_row(row: Row[Any]) -> BelowCostRow:
        (
            product_id,
            sku,
            name,
            currency_code,
            price_minor,
            location_id,
            location_name,
            quantity,
            value_minor,
        ) = row._tuple()
        currency = Currency(currency_code)
        average_minor = _round_half_up(int(value_minor or 0), quantity)
        return BelowCostRow(
            product_id=product_id,
            sku=sku,
            product_name=name,
            location_id=location_id,
            location_name=location_name,
            quantity=quantity,
            catalog_price=Money(int(price_minor), currency),
            average_unit_cost=Money(average_minor, currency),
        )
