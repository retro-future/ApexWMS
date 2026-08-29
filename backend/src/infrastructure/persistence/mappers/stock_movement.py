from domain.entities import StockMovement
from domain.enums import DocumentType, MovementType
from infrastructure.persistence.tenant.models import StockMovementModel


class StockMovementMapper:
    model: type[StockMovementModel] = StockMovementModel

    def to_entity(self, model: StockMovementModel) -> StockMovement:
        return StockMovement(
            id=model.id,
            occurred_at=model.occurred_at,
            movement_type=MovementType(model.movement_type),
            product_id=model.product_id,
            device_unit_id=model.device_unit_id,
            location_id=model.location_id,
            quantity_delta=model.quantity_delta,
            document_type=DocumentType(model.document_type),
            document_id=model.document_id,
            user_id=model.user_id,
            note=model.note,
        )

    def to_model(
        self, entity: StockMovement, model: StockMovementModel | None = None
    ) -> StockMovementModel:
        model = model or StockMovementModel(id=entity.id)
        model.occurred_at = entity.occurred_at
        model.movement_type = entity.movement_type.value
        model.product_id = entity.product_id
        model.device_unit_id = entity.device_unit_id
        model.location_id = entity.location_id
        model.quantity_delta = entity.quantity_delta
        model.document_type = entity.document_type.value
        model.document_id = entity.document_id
        model.user_id = entity.user_id
        model.note = entity.note
        return model
