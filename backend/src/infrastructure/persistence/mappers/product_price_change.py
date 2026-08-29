from domain.entities import ProductPriceChange
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import ProductPriceChangeModel


class ProductPriceChangeMapper:
    model: type[ProductPriceChangeModel] = ProductPriceChangeModel

    def to_entity(self, model: ProductPriceChangeModel) -> ProductPriceChange:
        currency = Currency(model.product.currency)
        return ProductPriceChange(
            id=model.id,
            product_id=model.product_id,
            occurred_at=model.occurred_at,
            old_price=(
                Money(model.old_price_minor, currency)
                if model.old_price_minor is not None
                else None
            ),
            new_price=Money(model.new_price_minor, currency),
            reason=model.reason,
            user_id=model.user_id,
        )

    def to_model(
        self, entity: ProductPriceChange, model: ProductPriceChangeModel | None = None
    ) -> ProductPriceChangeModel:
        model = model or ProductPriceChangeModel(id=entity.id)
        model.product_id = entity.product_id
        model.occurred_at = entity.occurred_at
        model.old_price_minor = entity.old_price.amount_minor if entity.old_price else None
        model.new_price_minor = entity.new_price.amount_minor
        model.reason = entity.reason
        model.user_id = entity.user_id
        return model
