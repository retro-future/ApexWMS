from domain.entities import SupplierReturn, SupplierReturnLine
from domain.enums import DocumentStatus, SupplierReturnReason, TrackingType
from domain.value_objects import Currency
from infrastructure.persistence.tenant.models import (
    SupplierReturnLineModel,
    SupplierReturnModel,
)


class SupplierReturnMapper:
    """Sole mapper for the SupplierReturn aggregate: lines included.

    Unlike the purchase order, a return's lines are added and removed by
    scanning while it is a draft, so ``to_model``'s update path is a full
    id-keyed collection sync, not a price-only touch.
    """

    model: type[SupplierReturnModel] = SupplierReturnModel

    def to_entity(self, model: SupplierReturnModel) -> SupplierReturn:
        return SupplierReturn(
            id=model.id,
            number=model.number,
            status=DocumentStatus(model.status),
            supplier_id=model.supplier_id,
            location_id=model.location_id,
            reason=SupplierReturnReason(model.reason),
            note=model.note,
            created_by=model.created_by,
            created_at=model.created_at,
            confirmed_by=model.confirmed_by,
            confirmed_at=model.confirmed_at,
            cancelled_by=model.cancelled_by,
            cancelled_at=model.cancelled_at,
            cancellation_reason=model.cancellation_reason,
            lines=[self._line_to_entity(line) for line in model.lines],
        )

    def _line_to_entity(self, model: SupplierReturnLineModel) -> SupplierReturnLine:
        return SupplierReturnLine(
            id=model.id,
            supplier_return_id=model.supplier_return_id,
            product_id=model.product_id,
            device_unit_id=model.device_unit_id,
            quantity=model.quantity,
            currency=Currency(model.product.currency),
            tracking_type=TrackingType(model.product.tracking_type),
            imei=None if model.device_unit is None else model.device_unit.imei,
        )

    def to_model(
        self, entity: SupplierReturn, model: SupplierReturnModel | None = None
    ) -> SupplierReturnModel:
        fresh = model is None
        model = model or SupplierReturnModel(id=entity.id)
        model.status = entity.status.value
        model.reason = entity.reason.value
        model.note = entity.note
        model.confirmed_by = entity.confirmed_by
        model.confirmed_at = entity.confirmed_at
        model.cancelled_by = entity.cancelled_by
        model.cancelled_at = entity.cancelled_at
        model.cancellation_reason = entity.cancellation_reason
        if fresh:
            model.number = entity.number
            model.supplier_id = entity.supplier_id
            model.location_id = entity.location_id
            model.created_by = entity.created_by
            model.created_at = entity.created_at
        self._sync_lines(entity, model)
        return model

    @staticmethod
    def _line_to_model(entity: SupplierReturnLine) -> SupplierReturnLineModel:
        return SupplierReturnLineModel(
            id=entity.id,
            product_id=entity.product_id,
            device_unit_id=entity.device_unit_id,
            quantity=entity.quantity,
        )

    def _sync_lines(self, entity: SupplierReturn, model: SupplierReturnModel) -> None:
        want = {line.id: line for line in entity.lines}
        for row in list(model.lines):
            line = want.get(row.id)
            if line is None:
                model.lines.remove(row)  # cascade delete-orphan issues the DELETE
            else:
                row.quantity = line.quantity
        have = {row.id for row in model.lines}
        for line in entity.lines:
            if line.id not in have:
                model.lines.append(self._line_to_model(line))
