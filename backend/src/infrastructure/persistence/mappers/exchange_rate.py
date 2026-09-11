from domain.entities import ExchangeRate
from domain.enums import RateKind
from infrastructure.persistence.tenant.models import ExchangeRateModel


class ExchangeRateMapper:
    model: type[ExchangeRateModel] = ExchangeRateModel

    def to_entity(self, model: ExchangeRateModel) -> ExchangeRate:
        return ExchangeRate(
            id=model.id,
            kind=RateKind(model.kind),
            effective_on=model.effective_on,
            som_per_usd=model.som_per_usd,
            user_id=model.user_id,
            set_at=model.set_at,
        )

    def to_model(
        self, entity: ExchangeRate, model: ExchangeRateModel | None = None
    ) -> ExchangeRateModel:
        model = model or ExchangeRateModel(id=entity.id)
        model.kind = entity.kind.value
        model.effective_on = entity.effective_on
        model.som_per_usd = entity.som_per_usd
        model.user_id = entity.user_id
        model.set_at = entity.set_at
        return model
