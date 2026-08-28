from domain.entities import PurchaseOrder, PurchaseOrderLine
from domain.enums import DocumentStatus, TrackingType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    PurchaseOrderLineModel,
    PurchaseOrderModel,
)


class PurchaseOrderMapper:
    """Sole mapper for the PurchaseOrder aggregate: lines included.

    A line's currency and tracking type come from its product row, reached
    through the ``product`` relationship the specification eager-loads.
    """

    model: type[PurchaseOrderModel] = PurchaseOrderModel

    def to_entity(self, model: PurchaseOrderModel) -> PurchaseOrder:
        return PurchaseOrder(
            id=model.id,
            number=model.number,
            status=DocumentStatus(model.status),
            supplier_id=model.supplier_id,
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

    def _line_to_entity(self, model: PurchaseOrderLineModel) -> PurchaseOrderLine:
        currency = Currency(model.product.currency)
        return PurchaseOrderLine(
            id=model.id,
            purchase_order_id=model.purchase_order_id,
            product_id=model.product_id,
            quantity=model.quantity,
            unit_cost=(
                None
                if model.unit_cost_minor is None
                else Money(model.unit_cost_minor, currency)
            ),
            currency=currency,
            tracking_type=TrackingType(model.product.tracking_type),
        )

    def to_model(
        self, entity: PurchaseOrder, model: PurchaseOrderModel | None = None
    ) -> PurchaseOrderModel:
        fresh = model is None
        model = model or PurchaseOrderModel(id=entity.id)
        model.status = entity.status.value
        model.supplier_id = entity.supplier_id
        model.note = entity.note
        model.confirmed_by = entity.confirmed_by
        model.confirmed_at = entity.confirmed_at
        model.cancelled_by = entity.cancelled_by
        model.cancelled_at = entity.cancelled_at
        model.cancellation_reason = entity.cancellation_reason
        if fresh:
            model.number = entity.number
            model.created_by = entity.created_by
            model.created_at = entity.created_at
            model.lines = [self._line_to_model(line) for line in entity.lines]
        else:
            self._sync_line_prices(entity, model)
        return model

    def _line_to_model(self, entity: PurchaseOrderLine) -> PurchaseOrderLineModel:
        return PurchaseOrderLineModel(
            id=entity.id,
            product_id=entity.product_id,
            quantity=entity.quantity,
            unit_cost_minor=(
                entity.unit_cost.amount_minor if entity.unit_cost else None
            ),
        )

    @staticmethod
    def _sync_line_prices(entity: PurchaseOrder, model: PurchaseOrderModel) -> None:
        """Pricing is the only post-creation change to a line (FR-3.1).

        Lines are never added or removed on a draft order, so this copies
        ``unit_cost_minor`` onto the matching existing child and does no
        insert or delete.
        """
        by_id = {line.id: line for line in entity.lines}
        for row in model.lines:
            line = by_id.get(row.id)
            if line is not None:
                row.unit_cost_minor = (
                    line.unit_cost.amount_minor if line.unit_cost else None
                )
