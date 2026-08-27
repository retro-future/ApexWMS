"""The stock ledger (PRD §4.3).

A movement counts goods and carries no currency; the money side of the same
event lives in ``financial_transactions``, written in the same database
transaction (FR-10.1). Every read is on the raw table except FR-9.5's log,
which joins the four names an operator recognises rather than showing them
the ids the ledger stores.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Row, func, select

from application.dtos import LedgerActor, MovementLogRow
from domain.entities import StockMovement
from domain.enums import DocumentType, MovementType
from infrastructure.persistence.tenant.models import (
    DeviceUnitModel,
    EmployeeModel,
    LocationModel,
    ProductModel,
    StockMovementModel,
)

from .base import TenantRepository
from .document_ref import document_number


class SqlStockMovementRepository(TenantRepository):
    """Append and read. There is no ``update`` — a mistake is corrected by
    appending its compensation (§4.3 rule 2), which is why the method is
    absent from ``AppendOnlyRepository``, the port handlers depend on."""

    def _to_model(self, entity: StockMovement) -> StockMovementModel:
        return StockMovementModel(
            id=entity.id,
            occurred_at=entity.occurred_at,
            movement_type=entity.movement_type.value,
            product_id=entity.product_id,
            device_unit_id=entity.device_unit_id,
            location_id=entity.location_id,
            quantity_delta=entity.quantity_delta,
            document_type=entity.document_type.value,
            document_id=entity.document_id,
            user_id=entity.user_id,
            note=entity.note,
        )

    def _to_entity(self, row: StockMovementModel) -> StockMovement:
        return StockMovement(
            id=row.id,
            occurred_at=row.occurred_at,
            movement_type=MovementType(row.movement_type),
            product_id=row.product_id,
            device_unit_id=row.device_unit_id,
            location_id=row.location_id,
            quantity_delta=row.quantity_delta,
            document_type=DocumentType(row.document_type),
            document_id=row.document_id,
            user_id=row.user_id,
            note=row.note,
        )

    async def add(self, entity: StockMovement) -> None:
        await self._insert(self._to_model(entity))

    async def list_for_document(
        self, document_type: DocumentType, document_id: UUID
    ) -> list[StockMovement]:
        """Everything one document wrote — what a cancellation compensates.

        Ordered so a reversal is written in the same sequence as the
        original, which keeps a document's timeline readable rather than
        interleaved.
        """
        return await self._many(
            select(StockMovementModel)
            .where(
                StockMovementModel.document_type == document_type.value,
                StockMovementModel.document_id == document_id,
            )
            .order_by(StockMovementModel.occurred_at, StockMovementModel.id),
            self._to_entity,
        )

    async def list_for_unit(self, device_unit_id: UUID) -> list[StockMovement]:
        """One handset's whole life, in order — the IMEI trace (FR-9.2).

        *"How did this IMEI end up here, and who touched it?"* is one table
        ordered by time, which is the entire payoff of §4.3.
        """
        return await self._many(
            select(StockMovementModel)
            .where(StockMovementModel.device_unit_id == device_unit_id)
            .order_by(StockMovementModel.occurred_at, StockMovementModel.id),
            self._to_entity,
        )

    async def net_quantity(self, product_id: UUID, location_id: UUID) -> int:
        """The level the ledger implies for one (product, location) pair.

        This is the *source* half of ``verify-projections``: the sum here is
        the truth, and ``stock_levels`` is what gets checked against it.
        """
        total = await self._session.scalar(
            select(func.sum(StockMovementModel.quantity_delta)).where(
                StockMovementModel.product_id == product_id,
                StockMovementModel.location_id == location_id,
            )
        )
        # Postgres widens an aggregate beyond its column type, so this
        # arrives as a Decimal on a real database and an int against a
        # fake. Both are whole numbers; only the type differs.
        return int(total or 0)

    async def list_for_pair(
        self, product_id: UUID, location_id: UUID
    ) -> list[StockMovement]:
        """One quantity product's movements at one location, in order."""
        return await self._many(
            select(StockMovementModel)
            .where(
                StockMovementModel.product_id == product_id,
                StockMovementModel.location_id == location_id,
                StockMovementModel.device_unit_id.is_(None),
            )
            .order_by(StockMovementModel.occurred_at, StockMovementModel.id),
            self._to_entity,
        )

    async def list_units_on_hand(self) -> list[UUID]:
        """Every handset the **ledger** says the store still holds.

        The counterpart to ``DeviceUnitRepository.list_on_hand``, which
        answers the same question from the projection. Auditing needs both:
        a unit silently marked ``SOLD`` vanishes from the projection side
        and would otherwise never be looked at again — which is the drift
        most worth catching, since the phone is still on the shelf.
        """
        rows = await self._session.scalars(
            select(StockMovementModel.device_unit_id)
            .where(StockMovementModel.device_unit_id.is_not(None))
            .group_by(StockMovementModel.device_unit_id)
            .having(func.sum(StockMovementModel.quantity_delta) > 0)
        )
        # The WHERE already excludes NULLs; the filter is what narrows the
        # column's ``UUID | None`` to ``UUID`` for the type checker.
        return [unit_id for unit_id in rows if unit_id is not None]

    async def list_moved_pairs(self) -> list[tuple[UUID, UUID]]:
        """Every (product, location) the ledger has ever touched.

        The sweep verify-projections walks — driven off the ledger rather
        than off ``stock_levels``, because a level that was never written
        at all is exactly the drift worth catching.
        """
        rows = await self._session.execute(
            select(StockMovementModel.product_id, StockMovementModel.location_id)
            .where(StockMovementModel.device_unit_id.is_(None))
            .distinct()
        )
        return [(product_id, location_id) for product_id, location_id in rows]

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
        """FR-9.5: the raw ledger, newest first, with names instead of ids.

        Every filter is optional and they compose, because the question this
        answers is never the same twice — *"what happened to this handset"*,
        *"what did this person move last week"*, *"what came into the
        warehouse"*.
        """
        number = document_number(
            StockMovementModel.document_type, StockMovementModel.document_id
        )
        stmt = (
            select(
                StockMovementModel,
                ProductModel.sku,
                ProductModel.name,
                DeviceUnitModel.imei,
                LocationModel.name,
                EmployeeModel.full_name,
                number,
            )
            .join(ProductModel, ProductModel.id == StockMovementModel.product_id)
            .join(LocationModel, LocationModel.id == StockMovementModel.location_id)
            # Left: a quantity line moves no handset (§4.1), and an employee
            # removed from the store must not take their history with them.
            .outerjoin(
                DeviceUnitModel, DeviceUnitModel.id == StockMovementModel.device_unit_id
            )
            .outerjoin(EmployeeModel, EmployeeModel.id == StockMovementModel.user_id)
        )
        if product_id is not None:
            stmt = stmt.where(StockMovementModel.product_id == product_id)
        if location_id is not None:
            stmt = stmt.where(StockMovementModel.location_id == location_id)
        if device_unit_id is not None:
            stmt = stmt.where(StockMovementModel.device_unit_id == device_unit_id)
        if user_id is not None:
            stmt = stmt.where(StockMovementModel.user_id == user_id)
        if movement_type is not None:
            stmt = stmt.where(StockMovementModel.movement_type == movement_type.value)
        if from_date is not None:
            stmt = stmt.where(StockMovementModel.occurred_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(StockMovementModel.occurred_at <= to_date)
        stmt = stmt.order_by(
            StockMovementModel.occurred_at.desc(), StockMovementModel.id
        )

        return await self._page_rows(stmt, page, page_size, self._to_log_row)

    @staticmethod
    def _to_log_row(
        row: Row[tuple[StockMovementModel, str, str, str, str, str, str | None]],
    ) -> MovementLogRow:
        movement, sku, product_name, scanned, place, actor, number = row._tuple()
        # Nullable at runtime whatever the column type says: a quantity line
        # names no handset, and an outer join can leave the actor unnamed.
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

    async def units_sold(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        location_id: UUID | None = None,
    ) -> dict[UUID, int]:
        """FR-9.3: how many things left each shelf as a sale.

        The delta is negated because a sale takes goods off the shelf. A
        cancelled sale writes the positive counterpart under the same type
        (§4.3 rule 3), so it cancels out here with no category to exclude.
        """
        stmt = (
            select(
                StockMovementModel.location_id,
                func.sum(-StockMovementModel.quantity_delta),
            )
            .where(StockMovementModel.movement_type == MovementType.SALE.value)
            .group_by(StockMovementModel.location_id)
        )
        if from_date is not None:
            stmt = stmt.where(StockMovementModel.occurred_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(StockMovementModel.occurred_at <= to_date)
        if location_id is not None:
            stmt = stmt.where(StockMovementModel.location_id == location_id)
        rows = await self._session.execute(stmt)
        return {place: int(sold or 0) for place, sold in rows.all()}

    async def trace_for_unit(self, device_unit_id: UUID) -> list[MovementLogRow]:
        """FR-9.2's ledger half: one handset's movements, oldest first.

        The same joined shape ``list_page`` returns, unpaged and in forward
        order, because a trace is read as a story rather than browsed.
        """
        rows, _ = await self.list_page(
            page=1,
            # A handset that has moved more times than this does not exist;
            # the trace is a life, not a feed.
            page_size=200,
            device_unit_id=device_unit_id,
        )
        return sorted(rows, key=lambda row: row.occurred_at)
