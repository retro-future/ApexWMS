from uuid import UUID

from domain.entities import CreditCompany
from infrastructure.persistence.tenant.models import CreditCompanyModel

from .base import TenantCrudRepository


class SqlCreditCompanyRepository(
    TenantCrudRepository[CreditCompany, UUID, CreditCompanyModel]
):
    model = CreditCompanyModel

    def _to_entity(self, row: CreditCompanyModel) -> CreditCompany:
        return CreditCompany(
            id=row.id,
            name=row.name,
            contact_name=row.contact_name,
            phone=row.phone,
            email=row.email,
            is_active=row.is_active,
            created_at=row.created_at,
        )

    def _to_model(self, entity: CreditCompany) -> CreditCompanyModel:
        return CreditCompanyModel(
            id=entity.id,
            name=entity.name,
            contact_name=entity.contact_name,
            phone=entity.phone,
            email=entity.email,
            is_active=entity.is_active,
            created_at=entity.created_at,
        )

    def _apply(self, row: CreditCompanyModel, entity: CreditCompany) -> None:
        row.name = entity.name
        row.contact_name = entity.contact_name
        row.phone = entity.phone
        row.email = entity.email
        row.is_active = entity.is_active

    async def get_by_name(self, name: str) -> CreditCompany | None:
        return await self._find_one(CreditCompanyModel.name == name)

    async def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[CreditCompany], int]:
        return await self._browse_page(
            page,
            page_size,
            search,
            is_active,
            CreditCompanyModel.name,
            CreditCompanyModel.contact_name,
            CreditCompanyModel.phone,
        )
