"""Write-offs and the lines scanned onto them (PRD §4.4, §5.6).

The same shape as ``SqlSupplierReturnRepository``, against its own two
tables. See that module for why the join onto ``products`` is on every read
and why the two do not share a base.

``reason`` is filterable on the list because "what did theft cost us this
quarter" is the question FR-6.5's closed set exists to make answerable.
"""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import Row, delete, select

from domain.entities import WriteOff, WriteOffLine
from domain.enums import DocumentStatus, TrackingType, WriteOffReason
from domain.value_objects import Currency
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    ProductModel,
    WriteOffLineModel,
    WriteOffModel,
)

from .base import TenantRepository


class SqlWriteOffRepository(TenantRepository):
    async def get(self, key: UUID) -> WriteOff | None:
        row = await self._row(WriteOffModel, key)
        if row is None:
            return None
        lines = await self._lines_for([key])
        return self._to_entity(row, lines[key])

    async def add(self, entity: WriteOff) -> None:
        await self._insert(self._to_model(entity))
        for line in entity.lines:
            await self.add_line(line)

    async def update(self, entity: WriteOff) -> None:
        row = await self._require_row(WriteOffModel, entity.id)
        # The number, the author and the location are absent on purpose:
        # none of them can change once the write-off is open.
        row.status = entity.status.value
        row.reason = entity.reason.value
        row.note = entity.note
        row.confirmed_by = entity.confirmed_by
        row.confirmed_at = entity.confirmed_at
        row.cancelled_by = entity.cancelled_by
        row.cancelled_at = entity.cancelled_at
        row.cancellation_reason = entity.cancellation_reason

    async def add_line(self, line: WriteOffLine) -> None:
        await self._insert(
            WriteOffLineModel(
                id=line.id,
                write_off_id=line.write_off_id,
                product_id=line.product_id,
                device_unit_id=line.device_unit_id,
                quantity=line.quantity,
            )
        )

    async def update_line(self, line: WriteOffLine) -> None:
        row = await self._require_row(WriteOffLineModel, line.id)
        # Only the quantity moves — see ``SqlSupplierReturnRepository``.
        row.quantity = line.quantity

    async def remove_line(self, line_id: UUID) -> None:
        await self._session.execute(
            delete(WriteOffLineModel).where(WriteOffLineModel.id == line_id)
        )

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        status: DocumentStatus | None = None,
        location_id: UUID | None = None,
        reason: WriteOffReason | None = None,
    ) -> tuple[list[WriteOff], int]:
        stmt = select(WriteOffModel)
        if search:
            stmt = stmt.where(WriteOffModel.number.ilike(f"%{search.strip()}%"))
        if status is not None:
            stmt = stmt.where(WriteOffModel.status == status.value)
        if location_id is not None:
            stmt = stmt.where(WriteOffModel.location_id == location_id)
        if reason is not None:
            stmt = stmt.where(WriteOffModel.reason == reason.value)
        stmt = stmt.order_by(WriteOffModel.created_at.desc(), WriteOffModel.id)

        rows, total = await self._page(stmt, page, page_size, lambda row: row)
        lines = await self._lines_for([row.id for row in rows])
        return [self._to_entity(row, lines[row.id]) for row in rows], total

    async def _lines_for(
        self, write_off_ids: list[UUID]
    ) -> defaultdict[UUID, list[WriteOffLine]]:
        lines: defaultdict[UUID, list[WriteOffLine]] = defaultdict(list)
        if not write_off_ids:
            return lines

        stmt = (
            select(
                WriteOffLineModel,
                ProductModel.currency,
                ProductModel.tracking_type,
                DeviceUnitModel.imei,
            )
            .join(ProductModel, ProductModel.id == WriteOffLineModel.product_id)
            # Outer: an accessory line names no handset, and dropping those
            # rows would hide half the document.
            .outerjoin(
                DeviceUnitModel, DeviceUnitModel.id == WriteOffLineModel.device_unit_id
            )
            .where(WriteOffLineModel.write_off_id.in_(write_off_ids))
            .order_by(WriteOffLineModel.id)
        )
        for row in await self._session.execute(stmt):
            line = self._to_line(row)
            lines[line.write_off_id].append(line)
        return lines

    @staticmethod
    def _to_line(row: Row[tuple[WriteOffLineModel, str, str, str]]) -> WriteOffLine:
        model, currency_code, tracking_type, scanned = row._tuple()
        # Nullable at runtime whatever the column type says — the join onto
        # ``device_units`` is outer, because an accessory line names no
        # handset.
        imei: str | None = scanned
        return WriteOffLine(
            id=model.id,
            write_off_id=model.write_off_id,
            product_id=model.product_id,
            device_unit_id=model.device_unit_id,
            quantity=model.quantity,
            currency=Currency(currency_code),
            tracking_type=TrackingType(tracking_type),
            imei=imei,
        )

    @staticmethod
    def _to_model(entity: WriteOff) -> WriteOffModel:
        return WriteOffModel(
            id=entity.id,
            number=entity.number,
            status=entity.status.value,
            location_id=entity.location_id,
            reason=entity.reason.value,
            note=entity.note,
            created_by=entity.created_by,
            created_at=entity.created_at,
            confirmed_by=entity.confirmed_by,
            confirmed_at=entity.confirmed_at,
            cancelled_by=entity.cancelled_by,
            cancelled_at=entity.cancelled_at,
            cancellation_reason=entity.cancellation_reason,
        )

    @staticmethod
    def _to_entity(row: WriteOffModel, lines: list[WriteOffLine]) -> WriteOff:
        return WriteOff(
            id=row.id,
            number=row.number,
            status=DocumentStatus(row.status),
            location_id=row.location_id,
            reason=WriteOffReason(row.reason),
            note=row.note,
            created_by=row.created_by,
            created_at=row.created_at,
            confirmed_by=row.confirmed_by,
            confirmed_at=row.confirmed_at,
            cancelled_by=row.cancelled_by,
            cancelled_at=row.cancelled_at,
            cancellation_reason=row.cancellation_reason,
            lines=lines,
        )
