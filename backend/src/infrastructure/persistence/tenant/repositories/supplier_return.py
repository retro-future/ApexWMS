"""Supplier returns and the lines scanned onto them (PRD §4.4, §5.5).

Every read joins ``products``, for the reason all three document
repositories do: a line's currency and tracking type belong to the catalog
row it names (§4.5 rule 3, §4.1), so the line is rebuilt from a ``Row``.

``add_line``/``remove_line`` exist because a scan is one row: rewriting the
whole return per beep would put the document through the database on every
trigger pull, and §6 gives the round trip 200ms.

``update`` writes the header only. A return's lines are added and removed
by scanning, and nothing about a confirmed one changes in bulk the way an
invoice's price snapshots do.

Nearly identical to ``SqlWriteOffRepository``, and deliberately not sharing
a base with it: the two tables are different tables, and a third repository
base to hold what they have in common is exactly the taxonomy
``repositories/base.py`` exists to refuse.
"""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import Row, delete, select

from domain.entities import SupplierReturn, SupplierReturnLine
from domain.enums import DocumentStatus, SupplierReturnReason, TrackingType
from domain.value_objects import Currency
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    ProductModel,
    SupplierReturnLineModel,
    SupplierReturnModel,
)

from .base import TenantRepository


class SqlSupplierReturnRepository(TenantRepository):
    async def get(self, key: UUID) -> SupplierReturn | None:
        row = await self._row(SupplierReturnModel, key)
        if row is None:
            return None
        lines = await self._lines_for([key])
        return self._to_entity(row, lines[key])

    async def add(self, entity: SupplierReturn) -> None:
        await self._insert(self._to_model(entity))
        for line in entity.lines:
            await self.add_line(line)

    async def update(self, entity: SupplierReturn) -> None:
        row = await self._require_row(SupplierReturnModel, entity.id)
        # The number, the author, the supplier and the location are absent
        # on purpose: none of them can change once the return is open.
        row.status = entity.status.value
        row.reason = entity.reason.value
        row.note = entity.note
        row.confirmed_by = entity.confirmed_by
        row.confirmed_at = entity.confirmed_at
        row.cancelled_by = entity.cancelled_by
        row.cancelled_at = entity.cancelled_at
        row.cancellation_reason = entity.cancellation_reason

    async def add_line(self, line: SupplierReturnLine) -> None:
        await self._insert(
            SupplierReturnLineModel(
                id=line.id,
                supplier_return_id=line.supplier_return_id,
                product_id=line.product_id,
                device_unit_id=line.device_unit_id,
                quantity=line.quantity,
            )
        )

    async def update_line(self, line: SupplierReturnLine) -> None:
        row = await self._require_row(SupplierReturnLineModel, line.id)
        # Only the quantity moves. The product and the handset are absent on
        # purpose: a line naming the wrong phone is removed and re-scanned,
        # so the operator sees the checks run against the new one.
        row.quantity = line.quantity

    async def remove_line(self, line_id: UUID) -> None:
        await self._session.execute(
            delete(SupplierReturnLineModel).where(SupplierReturnLineModel.id == line_id)
        )

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        status: DocumentStatus | None = None,
        supplier_id: UUID | None = None,
        reason: SupplierReturnReason | None = None,
    ) -> tuple[list[SupplierReturn], int]:
        stmt = select(SupplierReturnModel)
        if search:
            stmt = stmt.where(SupplierReturnModel.number.ilike(f"%{search.strip()}%"))
        if status is not None:
            stmt = stmt.where(SupplierReturnModel.status == status.value)
        if supplier_id is not None:
            stmt = stmt.where(SupplierReturnModel.supplier_id == supplier_id)
        if reason is not None:
            stmt = stmt.where(SupplierReturnModel.reason == reason.value)
        # Newest first, with ``id`` breaking ties so a page boundary is stable.
        stmt = stmt.order_by(
            SupplierReturnModel.created_at.desc(), SupplierReturnModel.id
        )

        rows, total = await self._page(stmt, page, page_size, lambda row: row)
        lines = await self._lines_for([row.id for row in rows])
        return [self._to_entity(row, lines[row.id]) for row in rows], total

    async def _lines_for(
        self, return_ids: list[UUID]
    ) -> defaultdict[UUID, list[SupplierReturnLine]]:
        lines: defaultdict[UUID, list[SupplierReturnLine]] = defaultdict(list)
        if not return_ids:
            return lines

        stmt = (
            select(
                SupplierReturnLineModel,
                ProductModel.currency,
                ProductModel.tracking_type,
                DeviceUnitModel.imei,
            )
            .join(ProductModel, ProductModel.id == SupplierReturnLineModel.product_id)
            # Outer: an accessory line names no handset, and dropping those
            # rows would hide half the document.
            .outerjoin(
                DeviceUnitModel,
                DeviceUnitModel.id == SupplierReturnLineModel.device_unit_id,
            )
            .where(SupplierReturnLineModel.supplier_return_id.in_(return_ids))
            # Scan order is what the operator saw, and it is the only order
            # that means anything on this document.
            .order_by(SupplierReturnLineModel.id)
        )
        for row in await self._session.execute(stmt):
            line = self._to_line(row)
            lines[line.supplier_return_id].append(line)
        return lines

    @staticmethod
    def _to_line(
        row: Row[tuple[SupplierReturnLineModel, str, str, str]],
    ) -> SupplierReturnLine:
        model, currency_code, tracking_type, scanned = row._tuple()
        # Nullable at runtime whatever the column type says — the join onto
        # ``device_units`` is outer, because an accessory line names no
        # handset.
        imei: str | None = scanned
        return SupplierReturnLine(
            id=model.id,
            supplier_return_id=model.supplier_return_id,
            product_id=model.product_id,
            device_unit_id=model.device_unit_id,
            quantity=model.quantity,
            currency=Currency(currency_code),
            tracking_type=TrackingType(tracking_type),
            imei=imei,
        )

    @staticmethod
    def _to_model(entity: SupplierReturn) -> SupplierReturnModel:
        return SupplierReturnModel(
            id=entity.id,
            number=entity.number,
            status=entity.status.value,
            supplier_id=entity.supplier_id,
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
    def _to_entity(
        row: SupplierReturnModel, lines: list[SupplierReturnLine]
    ) -> SupplierReturn:
        return SupplierReturn(
            id=row.id,
            number=row.number,
            status=DocumentStatus(row.status),
            supplier_id=row.supplier_id,
            location_id=row.location_id,
            reason=SupplierReturnReason(row.reason),
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
