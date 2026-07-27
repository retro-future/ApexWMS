from uuid import UUID

from sqlalchemy import or_, select

from domain.entities import Customer
from infrastructure.persistence.tenant.models import CustomerModel

from .base import TenantCrudRepository


class SqlCustomerRepository(TenantCrudRepository[Customer, UUID, CustomerModel]):
    model = CustomerModel


    def _to_entity(self, row: CustomerModel) -> Customer:
        return Customer(
            id=row.id,
            full_name=row.full_name,
            phone=row.phone,
            is_active=row.is_active,
            created_at=row.created_at,
        )

    def _to_model(self, entity: Customer) -> CustomerModel:
        return CustomerModel(
            id=entity.id,
            full_name=entity.full_name,
            phone=entity.phone,
            is_active=entity.is_active,
            created_at=entity.created_at,
        )

    def _apply(self, row: CustomerModel, entity: Customer) -> None:
        row.full_name = entity.full_name
        row.phone = entity.phone
        row.is_active = entity.is_active

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Customer], int]:
        stmt = select(CustomerModel)
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(CustomerModel.full_name.ilike(term), CustomerModel.phone.ilike(term))
            )
        if is_active is not None:
            stmt = stmt.where(CustomerModel.is_active.is_(is_active))
        return await self._page(stmt.order_by(CustomerModel.created_at), page, page_size)
