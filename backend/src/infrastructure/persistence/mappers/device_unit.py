from domain.entities import DeviceUnit
from domain.enums import DeviceCondition, DeviceStatus, DocumentType
from domain.value_objects import IMEI, Currency, Money
from infrastructure.persistence.tenant.models import DeviceUnitModel


class DeviceUnitMapper:
    """A handset's money amounts are bare minor units denominated by its
    catalog row (§4.5 rule 3), so ``to_entity`` reads the currency off the
    eager-loaded ``product``. ``to_model``'s update path writes only the
    three projection fields a posting or the repricer may move.
    """

    model: type[DeviceUnitModel] = DeviceUnitModel

    def to_entity(self, model: DeviceUnitModel) -> DeviceUnit:
        currency = Currency(model.product.currency)
        return DeviceUnit(
            id=model.id,
            imei=IMEI(model.imei),
            imei2=IMEI(model.imei2) if model.imei2 else None,
            serial_number=model.serial_number,
            product_id=model.product_id,
            status=DeviceStatus(model.status),
            location_id=model.location_id,
            acquisition_cost=Money(model.acquisition_cost_minor, currency),
            asking_price=(
                Money(model.asking_price_minor, currency)
                if model.asking_price_minor is not None
                else None
            ),
            condition=DeviceCondition(model.condition),
            cash_paid_minor=model.cash_paid_minor,
            # The one amount on the row not in the product's currency, which
            # is the entire reason it is recorded separately (§4.5b).
            cash_paid_currency=(
                Currency(model.cash_paid_currency) if model.cash_paid_currency else None
            ),
            source_document_type=(
                DocumentType(model.source_document_type)
                if model.source_document_type
                else None
            ),
            source_document_id=model.source_document_id,
            created_at=model.created_at,
        )

    def to_model(
        self, entity: DeviceUnit, model: DeviceUnitModel | None = None
    ) -> DeviceUnitModel:
        fresh = model is None
        model = model or DeviceUnitModel(id=entity.id)
        # status, location and asking price are projections kept in step by
        # a ledger posting or the repricer; the update path writes only them.
        model.status = entity.status.value
        model.location_id = entity.location_id
        model.asking_price_minor = (
            entity.asking_price.amount_minor if entity.asking_price else None
        )
        model.condition = entity.condition.value
        if fresh:
            model.imei = str(entity.imei)
            model.imei2 = str(entity.imei2) if entity.imei2 else None
            model.serial_number = entity.serial_number
            model.product_id = entity.product_id
            model.acquisition_cost_minor = entity.acquisition_cost.amount_minor
            model.cash_paid_minor = entity.cash_paid_minor
            model.cash_paid_currency = (
                entity.cash_paid_currency.value if entity.cash_paid_currency else None
            )
            model.source_document_type = (
                entity.source_document_type.value
                if entity.source_document_type
                else None
            )
            model.source_document_id = entity.source_document_id
            model.created_at = entity.created_at
        return model
