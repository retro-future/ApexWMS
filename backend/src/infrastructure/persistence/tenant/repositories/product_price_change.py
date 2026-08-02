"""The catalog-price log (FR-2.19, FR-9.2b).

Every read joins ``products``. The log stores bare minor units, because a
product's currency is a property of the product and immutable once it has
history (§4.5 rule 3) — so the currency is fetched rather than duplicated,
and a row physically cannot disagree with the catalog entry it belongs to.
"""

from uuid import UUID

from sqlalchemy import Select, select

from domain.entities import ProductPriceChange
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import ProductModel, ProductPriceChangeModel

from .base import TenantLedgerRepository


class SqlProductPriceChangeRepository(
    TenantLedgerRepository[ProductPriceChange, ProductPriceChangeModel]
):
    model = ProductPriceChangeModel

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

    def _to_entity(self, row: ProductPriceChangeModel, currency: Currency) -> ProductPriceChange:
        return ProductPriceChange(
            id=row.id,
            product_id=row.product_id,
            occurred_at=row.occurred_at,
            old_price=(
                Money(row.old_price_minor, currency) if row.old_price_minor is not None else None
            ),
            new_price=Money(row.new_price_minor, currency),
            reason=row.reason,
            user_id=row.user_id,
        )

    async def list_for_product(self, product_id: UUID) -> list[ProductPriceChange]:
        rows = await self._session.execute(self._priced(product_id))
        return [self._to_entity(row, Currency(currency)) for row, currency in rows]

    async def latest_for_product(self, product_id: UUID) -> ProductPriceChange | None:
        stmt = self._priced(product_id).order_by(
            ProductPriceChangeModel.occurred_at.desc(), ProductPriceChangeModel.id.desc()
        )
        found = (await self._session.execute(stmt.limit(1))).first()
        if found is None:
            return None
        row, currency = found
        return self._to_entity(row, Currency(currency))

    def _priced(self, product_id: UUID) -> Select[tuple[ProductPriceChangeModel, str]]:
        """History rows for *product_id*, oldest first, each with its currency.

        The tie-break on ``id`` is not cosmetic: two changes made inside the
        same clock tick would otherwise order arbitrarily, and "which was
        the latest price" is exactly the question the projection asks.
        """
        return (
            select(ProductPriceChangeModel, ProductModel.currency)
            .join(ProductModel, ProductModel.id == ProductPriceChangeModel.product_id)
            .where(ProductPriceChangeModel.product_id == product_id)
            .order_by(ProductPriceChangeModel.occurred_at, ProductPriceChangeModel.id)
        )
