"""The catalog-price log reads (FR-2.19, FR-9.2b).

Written against ``ProductPriceChangeModel`` (ADR 0007). Every read eager-loads
``product`` because the amounts carry no currency of their own — it comes
from the catalog entry (§4.5 rule 3). Both specs also store ``product_id``
as a plain attribute so the in-memory fake can read it.
"""

from uuid import UUID

from sqlalchemy.orm import selectinload

from application.common.specification import Specification
from infrastructure.persistence.tenant.models import ProductPriceChangeModel

_WITH_CURRENCY = selectinload(ProductPriceChangeModel.product)


class PriceChangesForProduct(Specification[ProductPriceChangeModel]):
    """A product's whole price history, oldest first."""

    def __init__(self, product_id: UUID) -> None:
        super().__init__(ProductPriceChangeModel)
        self.product_id = product_id
        self.where(ProductPriceChangeModel.product_id == product_id)
        self.include(_WITH_CURRENCY)
        self.order(ProductPriceChangeModel.occurred_at, ProductPriceChangeModel.id)


class LatestPriceChangeForProduct(Specification[ProductPriceChangeModel]):
    """The row ``Product.default_sale_price`` is the projection of; used with
    ``find_one``."""

    def __init__(self, product_id: UUID) -> None:
        super().__init__(ProductPriceChangeModel)
        self.product_id = product_id
        self.where(ProductPriceChangeModel.product_id == product_id)
        self.include(_WITH_CURRENCY)
        self.order(
            ProductPriceChangeModel.occurred_at.desc(),
            ProductPriceChangeModel.id.desc(),
        )
