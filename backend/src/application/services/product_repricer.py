"""Catalog repricing (FR-2.19): the log row and its projection, together.

``Product.default_sale_price`` is *the latest row of*
``product_price_changes`` (§4.5b) — not a field that also happens to have
a history table beside it. So there is exactly one place that writes both,
and it is this one. A handler that assigned the price itself would leave
the projection describing a change the log never recorded, which is the
failure the log exists to make impossible.

What this deliberately does not do: touch confirmed documents (they
snapshot their own prices, FR-4.5b) or units (a `NEW` unit follows the
catalog at resolution time, a priced unit ignores it — FR-2.20). There is
no cascade here because there is nothing to cascade to.
"""

from application.common.repository import TenantAppendOnlyRepository
from application.dtos import CurrentUser
from application.ports import Clock
from domain.entities import Product, ProductPriceChange
from domain.errors import PriceCannotBeUnsetError
from domain.value_objects import Money
from infrastructure.persistence.tenant.models import ProductPriceChangeModel


class ProductRepricer:
    def __init__(
        self,
        changes: TenantAppendOnlyRepository[ProductPriceChange, ProductPriceChangeModel],
        clock: Clock,
        current: CurrentUser,
    ) -> None:
        self._changes = changes
        self._clock = clock
        self._current = current

    async def set_price(
        self, product: Product, new_price: Money | None, reason: str | None = None
    ) -> None:
        """Move *product* to *new_price*, appending the row that records it.

        A no-op when the price is unchanged: repricing a model to what it
        already costs is not an event, and writing it would put noise into
        the one report (FR-9.2b) that answers "when did this move?".
        """
        if new_price is None:
            if product.default_sale_price is None:
                return
            raise PriceCannotBeUnsetError(
                "a catalog price cannot be cleared once set (FR-2.19) — "
                "deactivate the product instead"
            )
        if product.default_sale_price == new_price:
            return

        await self._changes.add(
            ProductPriceChange(
                product_id=product.id,
                occurred_at=self._clock.now(),
                old_price=product.default_sale_price,
                new_price=new_price,
                reason=reason,
                user_id=self._current.user_id,
            )
        )
        product.default_sale_price = new_price
