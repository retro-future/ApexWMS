"""A catalog entry — *"iPhone 15 Pro 256GB Titanium"*, not a physical thing
(PRD §4.2).

Lives in one store's own database, so it carries no ``tenant_id``.

Two fields decide how everything downstream behaves, and both are
immutable once the product has movement history (FR-2.1):

- ``tracking_type`` forks every stock operation from M3 onward (§4.1).
- ``currency`` denominates this product's cost, its sale price, its COGS
  and its share of inventory value, start to finish (§4.5 rule 3).
  Changing it on a product that already has history would silently
  reinterpret every past amount by a factor of ~12 600.

There is one currency here, not one per amount: ``default_sale_price``
inherits it, and the invariant below is what keeps the two from drifting.
"""

from dataclasses import dataclass
from datetime import datetime

from domain.catalog import TrackingType
from domain.core import TenantEntity, UuidEntity
from domain.errors import BarcodeNotAllowedError, CurrencyMismatchError, InvalidMoneyError
from domain.value_objects import SKU, Barcode, Currency, Money

# FR-2.6: phones are bought and sold in dollars, accessories in som. A
# convenience, not a constraint — the creator may override it.
_DEFAULT_CURRENCY = {
    TrackingType.SERIAL: Currency.USD,
    TrackingType.QUANTITY: Currency.UZS,
}


@dataclass(eq=False, kw_only=True)
class Product(UuidEntity, TenantEntity):
    sku: SKU
    name: str
    brand: str | None = None
    model: str | None = None
    tracking_type: TrackingType
    currency: Currency
    barcode: Barcode | None = None
    default_sale_price: Money | None = None
    is_active: bool
    created_at: datetime

    def __post_init__(self) -> None:
        if self.barcode is not None and self.tracking_type is TrackingType.SERIAL:
            raise BarcodeNotAllowedError(
                "a SERIAL product is identified by IMEI, not by barcode (FR-2.3)"
            )
        if self.default_sale_price is None:
            return
        if self.default_sale_price.currency is not self.currency:
            raise CurrencyMismatchError(
                f"default sale price is {self.default_sale_price.currency.value} "
                f"but the product is priced in {self.currency.value}"
            )
        if self.default_sale_price.is_negative:
            raise InvalidMoneyError("default sale price may not be negative")

    @staticmethod
    def default_currency_for(tracking_type: TrackingType) -> Currency:
        """FR-2.6's default, so no call site has to remember which is which."""
        return _DEFAULT_CURRENCY[tracking_type]
