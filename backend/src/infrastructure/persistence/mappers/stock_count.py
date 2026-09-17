from domain.entities import StockCount, StockCountLine, StockCountUnit
from domain.enums import DocumentStatus
from domain.value_objects import IMEI, Currency, Money
from infrastructure.persistence.tenant.models import (
    StockCountLineModel,
    StockCountModel,
    StockCountUnitModel,
)


class StockCountMapper:
    """Sole mapper for the StockCount aggregate: units and lines included.

    Two child collections, both changing after the count opens — a unit is
    scanned, a line is counted, a surprise unit is removed — so ``to_model``'s
    update path is a full id-keyed sync of each.
    """

    model: type[StockCountModel] = StockCountModel

    def to_entity(self, model: StockCountModel) -> StockCount:
        return StockCount(
            id=model.id,
            number=model.number,
            status=DocumentStatus(model.status),
            location_id=model.location_id,
            note=model.note,
            created_by=model.created_by,
            created_at=model.created_at,
            closed_by=model.closed_by,
            closed_at=model.closed_at,
            confirmed_by=model.confirmed_by,
            confirmed_at=model.confirmed_at,
            cancelled_by=model.cancelled_by,
            cancelled_at=model.cancelled_at,
            cancellation_reason=model.cancellation_reason,
            units=[self._unit_to_entity(u) for u in model.units],
            lines=[self._line_to_entity(line) for line in model.lines],
        )

    def _unit_to_entity(self, model: StockCountUnitModel) -> StockCountUnit:
        cost = None
        if model.acquisition_cost_minor is not None and model.product is not None:
            cost = Money(model.acquisition_cost_minor, Currency(model.product.currency))
        return StockCountUnit(
            id=model.id,
            stock_count_id=model.stock_count_id,
            imei=IMEI(model.imei),
            device_unit_id=model.device_unit_id,
            product_id=model.product_id,
            expected=model.expected,
            scanned=model.scanned,
            acquisition_cost=cost,
        )

    def _line_to_entity(self, model: StockCountLineModel) -> StockCountLine:
        stated_cost = None
        if model.stated_unit_cost_minor is not None:
            stated_cost = Money(model.stated_unit_cost_minor, Currency(model.product.currency))
        return StockCountLine(
            id=model.id,
            stock_count_id=model.stock_count_id,
            product_id=model.product_id,
            expected_quantity=model.expected_quantity,
            counted_quantity=model.counted_quantity,
            stated_unit_cost=stated_cost,
        )

    def to_model(
        self, entity: StockCount, model: StockCountModel | None = None
    ) -> StockCountModel:
        fresh = model is None
        model = model or StockCountModel(id=entity.id)
        model.status = entity.status.value
        model.note = entity.note
        model.closed_by = entity.closed_by
        model.closed_at = entity.closed_at
        model.confirmed_by = entity.confirmed_by
        model.confirmed_at = entity.confirmed_at
        model.cancelled_by = entity.cancelled_by
        model.cancelled_at = entity.cancelled_at
        model.cancellation_reason = entity.cancellation_reason
        if fresh:
            model.number = entity.number
            model.location_id = entity.location_id
            model.created_by = entity.created_by
            model.created_at = entity.created_at
        self._sync_units(entity, model)
        self._sync_lines(entity, model)
        return model

    @staticmethod
    def _unit_to_model(entity: StockCountUnit) -> StockCountUnitModel:
        return StockCountUnitModel(
            id=entity.id,
            imei=str(entity.imei),
            device_unit_id=entity.device_unit_id,
            product_id=entity.product_id,
            expected=entity.expected,
            scanned=entity.scanned,
            acquisition_cost_minor=(
                None
                if entity.acquisition_cost is None
                else entity.acquisition_cost.amount_minor
            ),
        )

    def _sync_units(self, entity: StockCount, model: StockCountModel) -> None:
        want = {unit.id: unit for unit in entity.units}
        for row in list(model.units):
            unit = want.get(row.id)
            if unit is None:
                model.units.remove(row)  # cascade delete-orphan issues the DELETE
            else:
                row.scanned = unit.scanned
                row.device_unit_id = unit.device_unit_id
                row.product_id = unit.product_id
                row.acquisition_cost_minor = (
                    None
                    if unit.acquisition_cost is None
                    else unit.acquisition_cost.amount_minor
                )
        have = {row.id for row in model.units}
        for unit in entity.units:
            if unit.id not in have:
                model.units.append(self._unit_to_model(unit))

    @staticmethod
    def _line_to_model(entity: StockCountLine) -> StockCountLineModel:
        return StockCountLineModel(
            id=entity.id,
            product_id=entity.product_id,
            expected_quantity=entity.expected_quantity,
            counted_quantity=entity.counted_quantity,
            stated_unit_cost_minor=(
                None if entity.stated_unit_cost is None else entity.stated_unit_cost.amount_minor
            ),
        )

    def _sync_lines(self, entity: StockCount, model: StockCountModel) -> None:
        want = {line.id: line for line in entity.lines}
        for row in list(model.lines):
            line = want.get(row.id)
            if line is None:
                model.lines.remove(row)
            else:
                row.counted_quantity = line.counted_quantity
                row.stated_unit_cost_minor = (
                    None if line.stated_unit_cost is None else line.stated_unit_cost.amount_minor
                )
        have = {row.id for row in model.lines}
        for line in entity.lines:
            if line.id not in have:
                model.lines.append(self._line_to_model(line))
