"""Stock-ledger reads that return a read-model row or a scalar (§4.3).

Split off ``SqlStockMovementRepository`` when the aggregate moved to the
append-only generic repository. Same shape as ``SqlGoodsReceiptQueries``.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, Select, func, select

from application.dtos import InventoryValueRow, LedgerActor, MovementLogRow
from domain.enums import DocumentType, MovementType
from domain.value_objects import Currency, Money
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    EmployeeModel,
    LocationModel,
    ProductModel,
    StockMovementModel,
)
from infrastructure.persistence.tenant.queries.document_ref import document_number
from infrastructure.types import TenantSession

_M = StockMovementModel


class SqlStockMovementQueries:
    def __init__(self, session: TenantSession) -> None:
        self._session = session

    async def list_page(
        self,
        page: int,
        page_size: int,
        product_id: UUID | None = None,
        location_id: UUID | None = None,
        device_unit_id: UUID | None = None,
        user_id: UUID | None = None,
        movement_type: MovementType | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> tuple[list[MovementLogRow], int]:
        number = document_number(_M.document_type, _M.document_id)
        stmt = (
            select(
                _M,
                ProductModel.sku,
                ProductModel.name,
                DeviceUnitModel.imei,
                LocationModel.name,
                EmployeeModel.full_name,
                number,
            )
            .join(ProductModel, ProductModel.id == _M.product_id)
            .join(LocationModel, LocationModel.id == _M.location_id)
            # Left: a quantity line moves no handset, and an employee removed
            # from the store must not take their history with them.
            .outerjoin(DeviceUnitModel, DeviceUnitModel.id == _M.device_unit_id)
            .outerjoin(EmployeeModel, EmployeeModel.id == _M.user_id)
        )
        if product_id is not None:
            stmt = stmt.where(_M.product_id == product_id)
        if location_id is not None:
            stmt = stmt.where(_M.location_id == location_id)
        if device_unit_id is not None:
            stmt = stmt.where(_M.device_unit_id == device_unit_id)
        if user_id is not None:
            stmt = stmt.where(_M.user_id == user_id)
        if movement_type is not None:
            stmt = stmt.where(_M.movement_type == movement_type.value)
        if from_date is not None:
            stmt = stmt.where(_M.occurred_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(_M.occurred_at <= to_date)
        stmt = stmt.order_by(_M.occurred_at.desc(), _M.id)

        total = await self._count(stmt)
        rows = await self._session.execute(
            stmt.offset((page - 1) * page_size).limit(page_size)
        )
        return [self._to_log_row(row) for row in rows], total

    async def trace_for_unit(self, device_unit_id: UUID) -> list[MovementLogRow]:
        # A handset that has moved more than this does not exist; the trace
        # is a life, not a feed.
        rows, _ = await self.list_page(page=1, page_size=200, device_unit_id=device_unit_id)
        return sorted(rows, key=lambda row: row.occurred_at)

    async def units_sold(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[UUID, int]:
        stmt = (
            select(_M.location_id, func.sum(-_M.quantity_delta))
            .where(_M.movement_type == MovementType.SALE.value)
            .group_by(_M.location_id)
        )
        if from_date is not None:
            stmt = stmt.where(_M.occurred_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(_M.occurred_at <= to_date)
        if location_id is not None:
            stmt = stmt.where(_M.location_id == location_id)
        rows = await self._session.execute(stmt)
        return {place: int(sold or 0) for place, sold in rows.all()}

    async def net_quantity(self, product_id: UUID, location_id: UUID) -> int:
        total = await self._session.scalar(
            select(func.sum(_M.quantity_delta)).where(
                _M.product_id == product_id, _M.location_id == location_id
            )
        )
        # Postgres widens an aggregate beyond its column type — a Decimal on
        # a real database, an int against a fake. Both are whole.
        return int(total or 0)

    async def units_on_hand(self) -> list[UUID]:
        rows = await self._session.scalars(
            select(_M.device_unit_id)
            .where(_M.device_unit_id.is_not(None))
            .group_by(_M.device_unit_id)
            .having(func.sum(_M.quantity_delta) > 0)
        )
        return [unit_id for unit_id in rows if unit_id is not None]

    async def moved_pairs(self, as_of: datetime | None = None) -> list[tuple[UUID, UUID]]:
        stmt = select(_M.product_id, _M.location_id).where(_M.device_unit_id.is_(None))
        if as_of is not None:
            stmt = stmt.where(_M.occurred_at < as_of)
        rows = await self._session.execute(stmt.distinct())
        return [(product_id, location_id) for product_id, location_id in rows]

    async def serialized_value_at(
        self, as_of: datetime, location_id: UUID | None = None
    ) -> list[InventoryValueRow]:
        """Two passes over the same cutoff: which handsets the ledger still
        holds, and where each one's last movement left it. Transfers are a
        v2 feature, so today the second pass almost always agrees with the
        unit's own ``location_id`` — it is written off the ledger anyway,
        because that column is a projection and this figure is an audit."""
        on_hand = (
            select(_M.device_unit_id.label("unit_id"))
            .where(_M.device_unit_id.is_not(None), _M.occurred_at < as_of)
            .group_by(_M.device_unit_id)
            .having(func.sum(_M.quantity_delta) > 0)
            .subquery()
        )
        placed = (
            select(_M.device_unit_id.label("unit_id"), _M.location_id.label("location_id"))
            .where(_M.device_unit_id.is_not(None), _M.occurred_at < as_of)
            .distinct(_M.device_unit_id)
            .order_by(_M.device_unit_id, _M.occurred_at.desc(), _M.id)
            .subquery()
        )
        stmt = (
            select(
                placed.c.location_id,
                LocationModel.name,
                ProductModel.currency,
                func.count(),
                func.sum(DeviceUnitModel.acquisition_cost_minor),
            )
            .select_from(on_hand)
            .join(placed, placed.c.unit_id == on_hand.c.unit_id)
            .join(DeviceUnitModel, DeviceUnitModel.id == on_hand.c.unit_id)
            .join(ProductModel, ProductModel.id == DeviceUnitModel.product_id)
            .outerjoin(LocationModel, LocationModel.id == placed.c.location_id)
            .group_by(placed.c.location_id, LocationModel.name, ProductModel.currency)
            .order_by(LocationModel.name)
        )
        if location_id is not None:
            stmt = stmt.where(placed.c.location_id == location_id)
        rows = await self._session.execute(stmt)
        return [
            InventoryValueRow(
                location_id=place,
                location_name=name,
                quantity=int(quantity or 0),
                # Postgres widens SUM(BIGINT) to NUMERIC; Money refuses non-int.
                amount=Money(int(total or 0), Currency(currency)),
            )
            for place, name, currency, quantity, total in rows
        ]

    async def _count(self, stmt: Select[Any]) -> int:
        total = await self._session.scalar(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
        return total or 0

    @staticmethod
    def _to_log_row(
        row: Row[tuple[StockMovementModel, str, str, str, str, str, str | None]],
    ) -> MovementLogRow:
        movement, sku, product_name, scanned, place, actor, number = row._tuple()
        imei: str | None = scanned
        location_name: str | None = place
        actor_name: str | None = actor
        return MovementLogRow(
            id=movement.id,
            occurred_at=movement.occurred_at,
            movement_type=MovementType(movement.movement_type),
            quantity_delta=movement.quantity_delta,
            product_id=movement.product_id,
            sku=sku,
            product_name=product_name,
            device_unit_id=movement.device_unit_id,
            imei=imei,
            location_id=movement.location_id,
            location_name=location_name or "",
            document_type=DocumentType(movement.document_type),
            document_id=movement.document_id,
            document_number=number,
            actor=LedgerActor(user_id=movement.user_id, user_name=actor_name),
            note=movement.note,
        )
