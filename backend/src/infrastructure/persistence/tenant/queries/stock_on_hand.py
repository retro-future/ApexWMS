"""FR-9.1's two halves, read from the two tables that hold stock.

A reporting path rather than a method on either aggregate: the report spans
``device_units`` and ``stock_levels``, so putting it on one of them would
make the other a stranger to half its own answer.

The serialized half groups in SQL because a store holds far more handsets
than groups, and each one carries its own cost. The accessory half cannot:
an accessory's cost is a pool replayed from the two ledgers (§4.6), so this
returns the pairs and ``StockOnHandReader`` values them.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Row, func, null, select

from application.dtos import AccessoryOnHand, OnHandBucket, StockGroupBy
from domain.enums import TrackingType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    LocationModel,
    ProductModel,
    StockLevelModel,
)
from infrastructure.persistence.tenant.queries.device_unit import ON_HAND
from infrastructure.types import TenantSession

# A product with no brand is its own bucket rather than a null key, so the
# group survives the round trip and can be paged over like any other.
UNBRANDED = "(no brand)"


class SqlStockOnHandQueries:
    def __init__(self, session: TenantSession) -> None:
        self._session = session

    async def serialized_totals(
        self,
        group_by: StockGroupBy,
        location_id: UUID | None = None,
        product_id: UUID | None = None,
        brand: str | None = None,
    ) -> list[OnHandBucket]:
        key, label, sku = self._dimension(group_by)
        stmt = (
            select(
                key,
                label,
                sku,
                ProductModel.currency,
                func.count(DeviceUnitModel.id),
                func.sum(DeviceUnitModel.acquisition_cost_minor),
            )
            .join(ProductModel, ProductModel.id == DeviceUnitModel.product_id)
            .outerjoin(LocationModel, LocationModel.id == DeviceUnitModel.location_id)
            .where(
                DeviceUnitModel.status.in_(ON_HAND),
                *self._catalog_filters(product_id, brand),
            )
            .group_by(key, label, ProductModel.currency)
            .order_by(label)
        )
        if location_id is not None:
            stmt = stmt.where(DeviceUnitModel.location_id == location_id)
        rows = await self._session.execute(stmt)
        return [self._to_bucket(row) for row in rows]

    async def accessories_on_hand(
        self,
        group_by: StockGroupBy,
        location_id: UUID | None = None,
        product_id: UUID | None = None,
        brand: str | None = None,
    ) -> list[AccessoryOnHand]:
        key, label, sku = self._dimension(group_by)
        stmt = (
            select(
                StockLevelModel.product_id,
                StockLevelModel.location_id,
                StockLevelModel.quantity,
                key,
                label,
                sku,
            )
            .join(ProductModel, ProductModel.id == StockLevelModel.product_id)
            .join(LocationModel, LocationModel.id == StockLevelModel.location_id)
            .where(
                ProductModel.tracking_type == TrackingType.QUANTITY.value,
                StockLevelModel.quantity > 0,
                *self._catalog_filters(product_id, brand),
            )
            .order_by(label, StockLevelModel.product_id)
        )
        if location_id is not None:
            stmt = stmt.where(StockLevelModel.location_id == location_id)
        rows = await self._session.execute(stmt)
        return [self._to_accessory(row) for row in rows]

    @staticmethod
    def _dimension(
        group_by: StockGroupBy,
    ) -> tuple[ColumnElement[Any], ColumnElement[Any], ColumnElement[Any]]:
        """The key, the human label and the SKU both statements group by,
        stated once so the two halves cannot group differently. The SKU is
        only meaningful when grouping by product."""
        no_sku = null().label("group_sku")
        if group_by is StockGroupBy.PRODUCT:
            return (
                ProductModel.id.label("group_key"),
                ProductModel.name.label("group_label"),
                ProductModel.sku.label("group_sku"),
            )
        if group_by is StockGroupBy.BRAND:
            branded = func.coalesce(ProductModel.brand, UNBRANDED)
            return branded.label("group_key"), branded.label("group_label"), no_sku
        return (
            LocationModel.id.label("group_key"),
            LocationModel.name.label("group_label"),
            no_sku,
        )

    @staticmethod
    def _catalog_filters(
        product_id: UUID | None, brand: str | None
    ) -> list[ColumnElement[bool]]:
        filters: list[ColumnElement[bool]] = []
        if product_id is not None:
            filters.append(ProductModel.id == product_id)
        if brand is not None:
            filters.append(ProductModel.brand == brand)
        return filters

    @staticmethod
    def _to_bucket(row: Row[tuple[Any, Any, str | None, str, int, int]]) -> OnHandBucket:
        key, label, sku, currency_code, count, cost_minor = row._tuple()
        return OnHandBucket(
            key=key,
            label=label,
            sku=sku,
            quantity=count,
            # Postgres widens SUM(BIGINT) to NUMERIC, and Money refuses
            # anything that is not an int.
            value=Money(int(cost_minor or 0), Currency(currency_code)),
        )

    @staticmethod
    def _to_accessory(
        row: Row[tuple[UUID, UUID, int, Any, Any, str | None]],
    ) -> AccessoryOnHand:
        product_id, location_id, quantity, key, label, sku = row._tuple()
        return AccessoryOnHand(
            product_id=product_id,
            location_id=location_id,
            quantity=quantity,
            key=key,
            label=label,
            sku=sku,
        )
