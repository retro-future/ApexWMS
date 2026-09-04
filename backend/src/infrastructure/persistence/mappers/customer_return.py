from domain.entities import CustomerReturn, CustomerReturnLine
from domain.enums import CustomerReturnReason, DocumentStatus, TrackingType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    CustomerReturnLineModel,
    CustomerReturnModel,
)


class CustomerReturnMapper:
    """Sole mapper for the CustomerReturn aggregate: lines included.

    ``charged_price`` is read off the joined invoice line rather than stored
    again: it is the ceiling every refund is checked against, and a second
    copy could drift from the snapshot the sale actually took.
    """

    model: type[CustomerReturnModel] = CustomerReturnModel

    def to_entity(self, model: CustomerReturnModel) -> CustomerReturn:
        return CustomerReturn(
            id=model.id,
            number=model.number,
            status=DocumentStatus(model.status),
            sales_invoice_id=model.sales_invoice_id,
            customer_id=model.customer_id,
            location_id=model.location_id,
            reason=CustomerReturnReason(model.reason),
            debt_relief=(
                None
                if model.debt_relief_minor is None
                else Money(amount_minor=model.debt_relief_minor, currency=Currency.UZS)
            ),
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

    def _line_to_entity(self, model: CustomerReturnLineModel) -> CustomerReturnLine:
        currency = Currency(model.product.currency)
        # Non-null on any line a return can hold: the invoice is confirmed,
        # and confirming is what writes the snapshot (FR-4.5b1).
        charged = model.sales_invoice_line.charged_price_minor or 0
        return CustomerReturnLine(
            id=model.id,
            customer_return_id=model.customer_return_id,
            sales_invoice_line_id=model.sales_invoice_line_id,
            product_id=model.product_id,
            device_unit_id=model.device_unit_id,
            quantity=model.quantity,
            currency=currency,
            tracking_type=TrackingType(model.product.tracking_type),
            imei=None if model.device_unit is None else model.device_unit.imei,
            charged_price=Money(amount_minor=charged, currency=currency),
            sold_quantity=model.sales_invoice_line.quantity,
            refund_price=Money(
                amount_minor=model.refund_price_minor, currency=currency
            ),
            refund_approved_by=model.refund_approved_by,
            refund_note=model.refund_note,
        )

    def to_model(
        self, entity: CustomerReturn, model: CustomerReturnModel | None = None
    ) -> CustomerReturnModel:
        fresh = model is None
        model = model or CustomerReturnModel(id=entity.id)
        model.status = entity.status.value
        model.reason = entity.reason.value
        model.debt_relief_minor = (
            None if entity.debt_relief is None else entity.debt_relief.amount_minor
        )
        model.note = entity.note
        model.confirmed_by = entity.confirmed_by
        model.confirmed_at = entity.confirmed_at
        model.cancelled_by = entity.cancelled_by
        model.cancelled_at = entity.cancelled_at
        model.cancellation_reason = entity.cancellation_reason
        if fresh:
            model.number = entity.number
            model.sales_invoice_id = entity.sales_invoice_id
            model.customer_id = entity.customer_id
            model.location_id = entity.location_id
            model.created_by = entity.created_by
            model.created_at = entity.created_at
        self._sync_lines(entity, model)
        return model

    @staticmethod
    def _line_to_model(entity: CustomerReturnLine) -> CustomerReturnLineModel:
        return CustomerReturnLineModel(
            id=entity.id,
            sales_invoice_line_id=entity.sales_invoice_line_id,
            product_id=entity.product_id,
            device_unit_id=entity.device_unit_id,
            quantity=entity.quantity,
            refund_price_minor=entity.refund_price.amount_minor,
            refund_approved_by=entity.refund_approved_by,
            refund_note=entity.refund_note,
        )

    def _sync_lines(self, entity: CustomerReturn, model: CustomerReturnModel) -> None:
        want = {line.id: line for line in entity.lines}
        for row in list(model.lines):
            line = want.get(row.id)
            if line is None:
                model.lines.remove(row)  # cascade delete-orphan issues the DELETE
            else:
                row.quantity = line.quantity
                row.refund_price_minor = line.refund_price.amount_minor
                row.refund_approved_by = line.refund_approved_by
                row.refund_note = line.refund_note
        have = {row.id for row in model.lines}
        for line in entity.lines:
            if line.id not in have:
                model.lines.append(self._line_to_model(line))
