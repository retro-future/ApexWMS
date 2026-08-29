from domain.entities import FinancialTransaction
from domain.enums import DocumentType, TransactionType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import FinancialTransactionModel


class FinancialTransactionMapper:
    model: type[FinancialTransactionModel] = FinancialTransactionModel

    def to_entity(self, model: FinancialTransactionModel) -> FinancialTransaction:
        return FinancialTransaction(
            id=model.id,
            occurred_at=model.occurred_at,
            txn_type=TransactionType(model.txn_type),
            amount=Money(model.amount_minor, Currency(model.currency)),
            document_type=DocumentType(model.document_type),
            document_id=model.document_id,
            location_id=model.location_id,
            product_id=model.product_id,
            device_unit_id=model.device_unit_id,
            user_id=model.user_id,
            note=model.note,
        )

    def to_model(
        self,
        entity: FinancialTransaction,
        model: FinancialTransactionModel | None = None,
    ) -> FinancialTransactionModel:
        model = model or FinancialTransactionModel(id=entity.id)
        model.occurred_at = entity.occurred_at
        model.txn_type = entity.txn_type.value
        model.amount_minor = entity.amount.amount_minor
        model.currency = entity.amount.currency.value
        model.document_type = entity.document_type.value
        model.document_id = entity.document_id
        model.location_id = entity.location_id
        model.product_id = entity.product_id
        model.device_unit_id = entity.device_unit_id
        model.user_id = entity.user_id
        model.note = entity.note
        return model
