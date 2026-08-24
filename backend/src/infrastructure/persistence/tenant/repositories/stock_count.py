"""Stock counts, their expected quantities and every handset they know about.

Three levels reassembled into one aggregate, in three queries whatever the
page size — the shape ``SqlGoodsReceiptRepository`` uses.

The join onto ``products`` is **outer** here, and that is the one thing
that differs from the other document repositories: a scanned IMEI the store
has no row for names no product yet, so there is no catalog row to take a
currency from. Every row that carries a cost does name one
(``StockCountUnit.__post_init__`` refuses the alternative), so the amount is
never left without a currency to be read back in.

``add_units``/``add_lines`` take a whole sequence because the opening
snapshot writes the entire shelf at once (FR-6.1), which is a different
operation from ``add_unit``'s one beep of the scanner.
"""

from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Row, delete, select

from domain.entities import StockCount, StockCountLine, StockCountUnit
from domain.enums import DocumentStatus
from domain.value_objects import IMEI, Currency, Money
from infrastructure.persistence.tenant.models import (
    ProductModel,
    StockCountLineModel,
    StockCountModel,
    StockCountUnitModel,
)

from .base import TenantRepository


class SqlStockCountRepository(TenantRepository):
    async def get(self, key: UUID) -> StockCount | None:
        row = await self._row(StockCountModel, key)
        if row is None:
            return None
        units = await self._units_for([key])
        lines = await self._lines_for([key])
        return self._to_entity(row, units[key], lines[key])

    async def add(self, entity: StockCount) -> None:
        await self._insert(self._to_model(entity))
        await self.add_units(entity.units)
        await self.add_lines(entity.lines)

    async def update(self, entity: StockCount) -> None:
        row = await self._require_row(StockCountModel, entity.id)
        # The number, the author and the location are absent on purpose:
        # none of them can change once the count is open.
        row.status = entity.status.value
        row.note = entity.note
        row.closed_by = entity.closed_by
        row.closed_at = entity.closed_at
        row.confirmed_by = entity.confirmed_by
        row.confirmed_at = entity.confirmed_at
        row.cancelled_by = entity.cancelled_by
        row.cancelled_at = entity.cancelled_at
        row.cancellation_reason = entity.cancellation_reason

    async def add_unit(self, unit: StockCountUnit) -> None:
        await self._insert(self._unit_model(unit))

    async def add_units(self, units: Sequence[StockCountUnit]) -> None:
        for unit in units:
            await self._insert(self._unit_model(unit))

    async def update_unit(self, unit: StockCountUnit) -> None:
        row = await self._require_row(StockCountUnitModel, unit.id)
        # The IMEI and ``expected`` are absent on purpose: what the snapshot
        # expected is history, and a mis-scan is removed and scanned again.
        row.scanned = unit.scanned
        row.device_unit_id = unit.device_unit_id
        row.product_id = unit.product_id
        row.acquisition_cost_minor = (
            None if unit.acquisition_cost is None else unit.acquisition_cost.amount_minor
        )

    async def remove_unit(self, unit_id: UUID) -> None:
        await self._session.execute(
            delete(StockCountUnitModel).where(StockCountUnitModel.id == unit_id)
        )

    async def add_lines(self, lines: Sequence[StockCountLine]) -> None:
        for line in lines:
            await self._insert(
                StockCountLineModel(
                    id=line.id,
                    stock_count_id=line.stock_count_id,
                    product_id=line.product_id,
                    expected_quantity=line.expected_quantity,
                    counted_quantity=line.counted_quantity,
                )
            )

    async def update_line(self, line: StockCountLine) -> None:
        row = await self._require_row(StockCountLineModel, line.id)
        # Only the counted figure moves. What the books expected was fixed
        # when the count opened, and rewriting it would erase the
        # discrepancy the count exists to find.
        row.counted_quantity = line.counted_quantity

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        status: DocumentStatus | None = None,
        location_id: UUID | None = None,
    ) -> tuple[list[StockCount], int]:
        stmt = select(StockCountModel)
        if search:
            stmt = stmt.where(StockCountModel.number.ilike(f"%{search.strip()}%"))
        if status is not None:
            stmt = stmt.where(StockCountModel.status == status.value)
        if location_id is not None:
            stmt = stmt.where(StockCountModel.location_id == location_id)
        stmt = stmt.order_by(StockCountModel.created_at.desc(), StockCountModel.id)

        rows, total = await self._page(stmt, page, page_size, lambda row: row)
        ids = [row.id for row in rows]
        units = await self._units_for(ids)
        lines = await self._lines_for(ids)
        return [
            self._to_entity(row, units[row.id], lines[row.id]) for row in rows
        ], total

    async def _units_for(
        self, count_ids: list[UUID]
    ) -> defaultdict[UUID, list[StockCountUnit]]:
        units: defaultdict[UUID, list[StockCountUnit]] = defaultdict(list)
        if not count_ids:
            return units

        stmt = (
            select(StockCountUnitModel, ProductModel.currency)
            # Outer: a surprise IMEI names no product until somebody says
            # which model it is.
            .outerjoin(ProductModel, ProductModel.id == StockCountUnitModel.product_id)
            .where(StockCountUnitModel.stock_count_id.in_(count_ids))
            # By IMEI, because a count row has no sequence of its own and
            # the list has to read the same way on every request.
            .order_by(StockCountUnitModel.imei)
        )
        for row in await self._session.execute(stmt):
            unit = self._to_unit(row)
            units[unit.stock_count_id].append(unit)
        return units

    async def _lines_for(
        self, count_ids: list[UUID]
    ) -> defaultdict[UUID, list[StockCountLine]]:
        lines: defaultdict[UUID, list[StockCountLine]] = defaultdict(list)
        if not count_ids:
            return lines

        stmt = (
            select(StockCountLineModel)
            .where(StockCountLineModel.stock_count_id.in_(count_ids))
            .order_by(StockCountLineModel.product_id)
        )
        for row in await self._session.scalars(stmt):
            line = self._to_line(row)
            lines[line.stock_count_id].append(line)
        return lines

    @staticmethod
    def _unit_model(unit: StockCountUnit) -> StockCountUnitModel:
        return StockCountUnitModel(
            id=unit.id,
            stock_count_id=unit.stock_count_id,
            imei=str(unit.imei),
            device_unit_id=unit.device_unit_id,
            product_id=unit.product_id,
            expected=unit.expected,
            scanned=unit.scanned,
            acquisition_cost_minor=(
                None
                if unit.acquisition_cost is None
                else unit.acquisition_cost.amount_minor
            ),
        )

    @staticmethod
    def _to_unit(row: Row[tuple[StockCountUnitModel, str]]) -> StockCountUnit:
        model, selected = row._tuple()
        # Nullable at runtime whatever the column type says — the join onto
        # ``products`` is outer, because a surprise IMEI names no product
        # until somebody says which model it is.
        currency_code: str | None = selected
        cost = None
        if model.acquisition_cost_minor is not None and currency_code is not None:
            cost = Money(model.acquisition_cost_minor, Currency(currency_code))
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

    @staticmethod
    def _to_line(row: StockCountLineModel) -> StockCountLine:
        return StockCountLine(
            id=row.id,
            stock_count_id=row.stock_count_id,
            product_id=row.product_id,
            expected_quantity=row.expected_quantity,
            counted_quantity=row.counted_quantity,
        )

    @staticmethod
    def _to_model(entity: StockCount) -> StockCountModel:
        return StockCountModel(
            id=entity.id,
            number=entity.number,
            status=entity.status.value,
            location_id=entity.location_id,
            note=entity.note,
            created_by=entity.created_by,
            created_at=entity.created_at,
            closed_by=entity.closed_by,
            closed_at=entity.closed_at,
            confirmed_by=entity.confirmed_by,
            confirmed_at=entity.confirmed_at,
            cancelled_by=entity.cancelled_by,
            cancelled_at=entity.cancelled_at,
            cancellation_reason=entity.cancellation_reason,
        )

    @staticmethod
    def _to_entity(
        row: StockCountModel,
        units: list[StockCountUnit],
        lines: list[StockCountLine],
    ) -> StockCount:
        return StockCount(
            id=row.id,
            number=row.number,
            status=DocumentStatus(row.status),
            location_id=row.location_id,
            note=row.note,
            created_by=row.created_by,
            created_at=row.created_at,
            closed_by=row.closed_by,
            closed_at=row.closed_at,
            confirmed_by=row.confirmed_by,
            confirmed_at=row.confirmed_at,
            cancelled_by=row.cancelled_by,
            cancelled_at=row.cancelled_at,
            cancellation_reason=row.cancellation_reason,
            units=units,
            lines=lines,
        )
