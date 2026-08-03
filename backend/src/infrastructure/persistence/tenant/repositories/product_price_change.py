"""The catalog-price log (FR-2.19, FR-9.2b).

Every read joins ``products``. The log stores bare minor units, because a
product's currency is a property of the product and immutable once it has
history (§4.5 rule 3) — so the currency is fetched rather than duplicated,
and a row physically cannot disagree with the catalog entry it belongs to.

That join is why the entity is rebuilt from a ``Row`` rather than from the
log row alone, and why this is not a ``TenantCrudRepository``.
"""

from uuid import UUID

from sqlalchemy import Row, Select, select

from domain.entities import ProductPriceChange
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import ProductModel, ProductPriceChangeModel

from .base import TenantRepository


class SqlProductPriceChangeRepository(TenantRepository):
    """Append and read; never update — the port says so (§4.5b)."""

    def _to_model(self, entity: ProductPriceChange) -> ProductPriceChangeModel:
        return ProductPriceChangeModel(
            id=entity.id,
            product_id=entity.product_id,
            occurred_at=entity.occurred_at,
            old_price_minor=entity.old_price.amount_minor if entity.old_price else None,
            new_price_minor=entity.new_price.amount_minor,
            reason=entity.reason,
            user_id=entity.user_id,
        )

    def _to_entity(
        self, row: Row[tuple[ProductPriceChangeModel, str]]
    ) -> ProductPriceChange:
        change, currency_code = row._tuple()
        currency = Currency(currency_code)
        return ProductPriceChange(
            id=change.id,
            product_id=change.product_id,
            occurred_at=change.occurred_at,
            old_price=(
                Money(change.old_price_minor, currency)
                if change.old_price_minor is not None
                else None
            ),
            new_price=Money(change.new_price_minor, currency),
            reason=change.reason,
            user_id=change.user_id,
        )

    async def add(self, entity: ProductPriceChange) -> None:
        await self._insert(self._to_model(entity))

    async def list_for_product(self, product_id: UUID) -> list[ProductPriceChange]:
        return await self._many_rows(
            self._priced(product_id).order_by(
                ProductPriceChangeModel.occurred_at, ProductPriceChangeModel.id
            ),
            self._to_entity,
        )

    async def latest_for_product(self, product_id: UUID) -> ProductPriceChange | None:
        return await self._one_row(
            self._priced(product_id)
            .order_by(
                ProductPriceChangeModel.occurred_at.desc(),
                ProductPriceChangeModel.id.desc(),
            )
            .limit(1),
            self._to_entity,
        )

    def _priced(self, product_id: UUID) -> Select[tuple[ProductPriceChangeModel, str]]:
        """History rows for *product_id*, each with its currency — unordered.

        Ordering is left to the caller because SQLAlchemy *appends* to an
        existing ``ORDER BY``: a helper that sorted ascending here would
        silently outrank the descending sort ``latest_for_product`` needs,
        and hand it the oldest row.

        Both callers tie-break on ``id``, which is not cosmetic: two
        changes made inside the same clock tick would otherwise order
        arbitrarily, and "which was the latest price" is exactly the
        question the projection asks.
        """
        return (
            select(ProductPriceChangeModel, ProductModel.currency)
            .join(ProductModel, ProductModel.id == ProductPriceChangeModel.product_id)
            .where(ProductPriceChangeModel.product_id == product_id)
        )
