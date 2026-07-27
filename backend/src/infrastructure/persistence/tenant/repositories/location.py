from uuid import UUID

from sqlalchemy import select

from domain.entities import Location
from infrastructure.persistence.tenant.models import LocationModel

from .base import TenantCrudRepository


class SqlLocationRepository(TenantCrudRepository[Location, UUID, LocationModel]):
    model = LocationModel


    def _to_entity(self, row: LocationModel) -> Location:
        return Location(
            id=row.id, name=row.name, is_active=row.is_active, created_at=row.created_at
        )

    def _to_model(self, entity: Location) -> LocationModel:
        return LocationModel(
            id=entity.id,
            name=entity.name,
            is_active=entity.is_active,
            created_at=entity.created_at,
        )

    def _apply(self, row: LocationModel, entity: Location) -> None:
        row.name = entity.name
        row.is_active = entity.is_active

    async def get_by_name(self, name: str) -> Location | None:
        return await self._find_one(LocationModel.name == name)

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Location], int]:
        stmt = select(LocationModel)
        if search:
            stmt = stmt.where(LocationModel.name.ilike(f"%{search.strip()}%"))
        if is_active is not None:
            stmt = stmt.where(LocationModel.is_active.is_(is_active))
        return await self._page(stmt.order_by(LocationModel.created_at), page, page_size)
