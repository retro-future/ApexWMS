from uuid import UUID

from sqlalchemy import select

from domain.entities import Tenant
from domain.tenancy import TenantStatus
from infrastructure.persistence.master.models import TenantModel

from .base import MasterCrudRepository


class SqlTenantRepository(MasterCrudRepository[Tenant, UUID, TenantModel]):
    model = TenantModel

    def _key(self, entity: Tenant) -> UUID:
        return entity.id

    def _to_entity(self, row: TenantModel) -> Tenant:
        return Tenant(
            id=row.id,
            name=row.name,
            slug=row.slug,
            status=TenantStatus(row.status),
            created_at=row.created_at,
        )

    def _to_model(self, entity: Tenant) -> TenantModel:
        return TenantModel(
            id=entity.id,
            name=entity.name,
            slug=entity.slug,
            status=entity.status.value,
            created_at=entity.created_at,
        )

    def _apply(self, row: TenantModel, entity: Tenant) -> None:
        row.name = entity.name
        row.slug = entity.slug
        row.status = entity.status.value

    async def get_by_slug(self, slug: str) -> Tenant | None:
        row = await self._session.scalar(select(TenantModel).where(TenantModel.slug == slug))
        return self._to_entity(row) if row else None

    async def list_all(self) -> list[Tenant]:
        rows = await self._session.scalars(select(TenantModel).order_by(TenantModel.created_at))
        return [self._to_entity(r) for r in rows]
