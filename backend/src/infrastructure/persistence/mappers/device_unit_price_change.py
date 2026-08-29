from domain.entities import DeviceUnitPriceChange
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import DeviceUnitPriceChangeModel


class DeviceUnitPriceChangeMapper:
    model: type[DeviceUnitPriceChangeModel] = DeviceUnitPriceChangeModel

    def to_entity(self, model: DeviceUnitPriceChangeModel) -> DeviceUnitPriceChange:
        currency = Currency(model.device_unit.product.currency)
        return DeviceUnitPriceChange(
            id=model.id,
            device_unit_id=model.device_unit_id,
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
        self,
        entity: DeviceUnitPriceChange,
        model: DeviceUnitPriceChangeModel | None = None,
    ) -> DeviceUnitPriceChangeModel:
        model = model or DeviceUnitPriceChangeModel(id=entity.id)
        model.device_unit_id = entity.device_unit_id
        model.occurred_at = entity.occurred_at
        model.old_price_minor = entity.old_price.amount_minor if entity.old_price else None
        model.new_price_minor = entity.new_price.amount_minor
        model.reason = entity.reason
        model.user_id = entity.user_id
        return model
