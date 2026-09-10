from domain.entities import Payment
from domain.enums import PaymentMethod
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import PaymentModel


class PaymentMapper:
    model: type[PaymentModel] = PaymentModel

    def to_entity(self, model: PaymentModel) -> Payment:
        return Payment(
            id=model.id,
            sales_invoice_id=model.sales_invoice_id,
            occurred_at=model.occurred_at,
            amount=Money(model.amount_minor, Currency(model.currency)),
            method=PaymentMethod(model.method),
            user_id=model.user_id,
            note=model.note,
            reverses_payment_id=model.reverses_payment_id,
        )

    def to_model(self, entity: Payment, model: PaymentModel | None = None) -> PaymentModel:
        model = model or PaymentModel(id=entity.id)
        model.sales_invoice_id = entity.sales_invoice_id
        model.occurred_at = entity.occurred_at
        model.amount_minor = entity.amount.amount_minor
        model.currency = entity.amount.currency.value
        model.method = entity.method.value
        model.user_id = entity.user_id
        model.note = entity.note
        model.reverses_payment_id = entity.reverses_payment_id
        return model
