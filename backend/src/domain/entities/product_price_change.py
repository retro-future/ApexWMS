"""One entry in a product's catalog-price history (PRD §4.5b, FR-2.19).

Changing the shelf price of a model governs **every future sale of every
unit of it**, so it is the higher-leverage of the two prices this system
tracks — and it was the one that would have been a silent ``UPDATE`` while
cutting a single handset by $40 left an immutable row naming its author.
So repricing is not an assignment; it is a row, and
``Product.default_sale_price`` is nothing more than the latest one.

The amounts carry no currency of their own. A product's currency is
immutable once it has movement history (§4.5 rule 3, FR-2.1), so every row
in a product's log is denominated in the same currency as the product —
the repository recovers it from ``products`` on read, and the invariant
below is what guarantees a row never disagrees with its predecessor.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.core import TenantEntity, UuidEntity
from domain.errors import CurrencyMismatchError, InvalidMoneyError
from domain.value_objects import Money


@dataclass(eq=False, kw_only=True)
class ProductPriceChange(UuidEntity, TenantEntity):
    product_id: UUID
    occurred_at: datetime
    # None only for the first pricing — a product created without a catalog
    # price, or created with one, has no predecessor to record.
    old_price: Money | None = None
    new_price: Money
    reason: str | None = None
    user_id: UUID

    def __post_init__(self) -> None:
        if self.new_price.is_negative:
            raise InvalidMoneyError("a catalog price may not be negative")
        if self.old_price is not None and self.old_price.currency is not self.new_price.currency:
            raise CurrencyMismatchError(
                f"repriced from {self.old_price.currency.value} to "
                f"{self.new_price.currency.value}, but a product's currency is immutable "
                "once it has history (FR-2.1)"
            )
