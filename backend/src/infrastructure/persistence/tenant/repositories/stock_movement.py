"""The stock ledger (PRD §4.3).

No join here, and no currency: a movement counts goods. The money side of
the same event lives in ``financial_transactions``, written in the same
database transaction (FR-10.1).
"""

from uuid import UUID

from sqlalchemy import func, select

from domain.entities import StockMovement
from domain.enums import DocumentType, MovementType
from infrastructure.persistence.tenant.models import StockMovementModel

from .base import TenantRepository


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
