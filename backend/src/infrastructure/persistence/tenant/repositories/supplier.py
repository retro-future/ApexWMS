from uuid import UUID

from sqlalchemy import or_, select

from domain.entities import Supplier
from infrastructure.persistence.tenant.models import SupplierModel

from .base import TenantCrudRepository


class SqlSupplierRepository(TenantCrudRepository[Supplier, UUID, SupplierModel]):
    model = SupplierModel


    def _to_entity(self, row: SupplierModel) -> Supplier:
        return Supplier(
            id=row.id,
            name=row.name,
            contact_name=row.contact_name,
            phone=row.phone,
            email=row.email,
            is_active=row.is_active,
            created_at=row.created_at,
        )

    def _to_model(self, entity: Supplier) -> SupplierModel:
        return SupplierModel(
            id=entity.id,
            name=entity.name,
            contact_name=entity.contact_name,
            phone=entity.phone,
            email=entity.email,
            is_active=entity.is_active,
            created_at=entity.created_at,
        )

    def _apply(self, row: SupplierModel, entity: Supplier) -> None:
        row.name = entity.name
        row.contact_name = entity.contact_name
        row.phone = entity.phone
        row.email = entity.email
        row.is_active = entity.is_active

    async def get_by_name(self, name: str) -> Supplier | None:
        return await self._find_one(SupplierModel.name == name)

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Supplier], int]:
        stmt = select(SupplierModel)
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    SupplierModel.name.ilike(term),
                    SupplierModel.contact_name.ilike(term),
                    SupplierModel.phone.ilike(term),
                )
            )
        if is_active is not None:
            stmt = stmt.where(SupplierModel.is_active.is_(is_active))
        return await self._page(stmt.order_by(SupplierModel.created_at), page, page_size)
