from domain.entities import Product
from domain.enums import TrackingType
from domain.value_objects import SKU, Barcode, Currency, Money
from infrastructure.persistence.tenant.models import ProductModel


class ProductMapper:
    model: type[ProductModel] = ProductModel

    def to_entity(self, model: ProductModel) -> Product:
        currency = Currency(model.currency)
        return Product(
            id=model.id,
            sku=SKU(model.sku),
            name=model.name,
            brand=model.brand,
            model=model.model,
            tracking_type=TrackingType(model.tracking_type),
            currency=currency,
            barcode=Barcode(model.barcode) if model.barcode else None,
            # The stored integer is only meaningful with its currency: USD
            # and UZS do not share an exponent (PRD §4.5).
            default_sale_price=(
                Money(model.default_sale_price_minor, currency)
                if model.default_sale_price_minor is not None
                else None
            ),
            is_active=model.is_active,
            created_at=model.created_at,
        )

    def to_model(self, entity: Product, model: ProductModel | None = None) -> ProductModel:
        price = entity.default_sale_price
        fresh = model is None
        model = model or ProductModel(id=entity.id)
        if fresh:
            # SKU, tracking type and currency are write-once (FR-2.1); the
            # update path never touches them.
            model.sku = str(entity.sku)
            model.tracking_type = entity.tracking_type.value
            model.currency = entity.currency.value
            model.created_at = entity.created_at
        model.name = entity.name
        model.brand = entity.brand
        model.model = entity.model
        model.barcode = str(entity.barcode) if entity.barcode else None
        model.default_sale_price_minor = price.amount_minor if price else None
        model.is_active = entity.is_active
        return model
