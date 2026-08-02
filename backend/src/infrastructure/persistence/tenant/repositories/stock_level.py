"""``(product, location) → quantity`` (§4.2).

A projection, so this repository is the only thing that writes it, and it
writes it only when a movement says to. ``get_for`` is keyed on the pair
rather than on an id because that pair is what the caller has in hand — a
movement — and it is what the unique constraint makes single-valued.
"""

from uuid import UUID

from sqlalchemy import select

from domain.entities import StockLevel
from infrastructure.persistence.tenant.models import StockLevelModel

from .base import TenantRowRepository


class SqlStockLevelRepository(TenantRowRepository[StockLevel, UUID, StockLevelModel]):
    model = StockLevelModel

    def _to_entity(self, row: StockLevelModel) -> StockLevel:
        return StockLevel(
            id=row.id,
            product_id=row.product_id,
            location_id=row.location_id,
            quantity=row.quantity,
        )

    def _to_model(self, entity: StockLevel) -> StockLevelModel:
        return StockLevelModel(
            id=entity.id,
            product_id=entity.product_id,
            location_id=entity.location_id,
            quantity=entity.quantity,
        )

    def _apply(self, row: StockLevelModel, entity: StockLevel) -> None:
        # Only the quantity moves: the pair is the row's identity, and
        # changing it would silently transfer stock between locations
        # without a movement to say so.
        row.quantity = entity.quantity

    async def get_for(self, product_id: UUID, location_id: UUID) -> StockLevel | None:
        return await self._find_one(
            StockLevelModel.product_id == product_id,
            StockLevelModel.location_id == location_id,
        )

    async def list_all(self) -> list[StockLevel]:
        """Every level in the store — the on-hand accessory value (§4.6)
        and the projection half of ``verify-projections``."""
        return await self._find_many(select(StockLevelModel))
