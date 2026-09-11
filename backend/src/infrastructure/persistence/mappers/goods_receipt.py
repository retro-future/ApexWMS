"""Sole mapper for the GoodsReceipt aggregate: lines and their scanned units.

Three levels. Lines are fixed at creation, so ``to_model``'s update path
matches them by id and never inserts or deletes one. A line's ``units`` are
scanned, priced and unscanned while the receipt is a draft, so each matched
line has its ``units`` collection synced the way ``StockCount`` syncs its two.

A line carries the product's currency and tracking type through a viewonly
``product`` relationship the spec eager-loads. A unit has no product of its
own: its money fields take the line's currency.
"""

from domain.entities import GoodsReceipt, GoodsReceiptLine, ReceivedUnit
from domain.enums import AcquisitionSource, DeviceCondition, DocumentStatus, TrackingType
from domain.value_objects import IMEI, Currency, Money
from infrastructure.persistence.tenant.models import (
    GoodsReceiptLineModel,
    GoodsReceiptModel,
    ReceivedUnitModel,
)


class GoodsReceiptMapper:
    model: type[GoodsReceiptModel] = GoodsReceiptModel

    def to_entity(self, model: GoodsReceiptModel) -> GoodsReceipt:
        return GoodsReceipt(
            id=model.id,
            number=model.number,
            status=DocumentStatus(model.status),
            acquisition_source=AcquisitionSource(model.acquisition_source),
            supplier_id=model.supplier_id,
            customer_id=model.customer_id,
            purchase_order_id=model.purchase_order_id,
            location_id=model.location_id,
            buyback_rate_id=model.buyback_rate_id,
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

    def _line_to_entity(self, model: GoodsReceiptLineModel) -> GoodsReceiptLine:
        currency = Currency(model.product.currency)
        return GoodsReceiptLine(
            id=model.id,
            goods_receipt_id=model.goods_receipt_id,
            product_id=model.product_id,
            quantity=model.quantity,
            unit_cost=(
                Money(model.unit_cost_minor, currency)
                if model.unit_cost_minor is not None
                else None
            ),
            tracking_type=TrackingType(model.product.tracking_type),
            currency=currency,
            units=[self._unit_to_entity(u, currency) for u in model.units],
        )

    @staticmethod
    def _unit_to_entity(model: ReceivedUnitModel, currency: Currency) -> ReceivedUnit:
        return ReceivedUnit(
            id=model.id,
            goods_receipt_line_id=model.goods_receipt_line_id,
            imei=IMEI(model.imei),
            imei2=IMEI(model.imei2) if model.imei2 else None,
            serial_number=model.serial_number,
            condition=DeviceCondition(model.condition),
            acquisition_cost=(
                Money(model.acquisition_cost_minor, currency)
                if model.acquisition_cost_minor is not None
                else None
            ),
            asking_price=(
                Money(model.asking_price_minor, currency)
                if model.asking_price_minor is not None
                else None
            ),
            cash_paid_minor=model.cash_paid_minor,
            cash_paid_currency=(
                Currency(model.cash_paid_currency) if model.cash_paid_currency else None
            ),
        )

    def to_model(
        self, entity: GoodsReceipt, model: GoodsReceiptModel | None = None
    ) -> GoodsReceiptModel:
        fresh = model is None
        model = model or GoodsReceiptModel(id=entity.id)
        # The number, the source and the parties cannot change once a receipt
        # is opened, so they are set only on the fresh path.
        model.status = entity.status.value
        model.note = entity.note
        model.confirmed_by = entity.confirmed_by
        model.confirmed_at = entity.confirmed_at
        model.cancelled_by = entity.cancelled_by
        model.cancelled_at = entity.cancelled_at
        model.cancellation_reason = entity.cancellation_reason
        # Stamped at confirm, so it belongs with status rather than the
        # fields fixed when the receipt was opened.
        model.buyback_rate_id = entity.buyback_rate_id
        if fresh:
            model.number = entity.number
            model.acquisition_source = entity.acquisition_source.value
            model.supplier_id = entity.supplier_id
            model.customer_id = entity.customer_id
            model.purchase_order_id = entity.purchase_order_id
            model.location_id = entity.location_id
            model.created_by = entity.created_by
            model.created_at = entity.created_at
            model.lines = [self._line_to_model(line) for line in entity.lines]
        else:
            self._sync_units(entity, model)
        return model

    def _line_to_model(self, entity: GoodsReceiptLine) -> GoodsReceiptLineModel:
        return GoodsReceiptLineModel(
            id=entity.id,
            product_id=entity.product_id,
            quantity=entity.quantity,
            unit_cost_minor=(
                entity.unit_cost.amount_minor if entity.unit_cost is not None else None
            ),
            units=[self._unit_to_model(u) for u in entity.units],
        )

    @staticmethod
    def _unit_to_model(entity: ReceivedUnit) -> ReceivedUnitModel:
        return ReceivedUnitModel(
            id=entity.id,
            imei=str(entity.imei),
            imei2=str(entity.imei2) if entity.imei2 else None,
            serial_number=entity.serial_number,
            condition=entity.condition.value,
            acquisition_cost_minor=(
                entity.acquisition_cost.amount_minor
                if entity.acquisition_cost is not None
                else None
            ),
            asking_price_minor=(
                entity.asking_price.amount_minor
                if entity.asking_price is not None
                else None
            ),
            cash_paid_minor=entity.cash_paid_minor,
            cash_paid_currency=(
                entity.cash_paid_currency.value if entity.cash_paid_currency else None
            ),
        )

    def _sync_units(self, entity: GoodsReceipt, model: GoodsReceiptModel) -> None:
        line_by_id = {line.id: line for line in entity.lines}
        for line_model in model.lines:
            line = line_by_id.get(line_model.id)
            if line is None:
                continue
            want = {unit.id: unit for unit in line.units}
            for row in list(line_model.units):
                unit = want.get(row.id)
                if unit is None:
                    line_model.units.remove(row)  # delete-orphan issues the DELETE
                else:
                    # The IMEI is left alone on purpose: a mis-scan is removed
                    # and scanned again so the duplicate check runs on the new one.
                    row.condition = unit.condition.value
                    row.acquisition_cost_minor = (
                        unit.acquisition_cost.amount_minor
                        if unit.acquisition_cost is not None
                        else None
                    )
                    row.asking_price_minor = (
                        unit.asking_price.amount_minor
                        if unit.asking_price is not None
                        else None
                    )
                    row.cash_paid_minor = unit.cash_paid_minor
                    row.cash_paid_currency = (
                        unit.cash_paid_currency.value
                        if unit.cash_paid_currency
                        else None
                    )
            have = {row.id for row in line_model.units}
            for unit in line.units:
                if unit.id not in have:
                    line_model.units.append(self._unit_to_model(unit))
