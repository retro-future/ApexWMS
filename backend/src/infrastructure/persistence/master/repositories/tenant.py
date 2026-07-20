from uuid import UUID

from domain.entities import Tenant
from domain.tenancy import TenantStatus
from infrastructure.persistence.master.models import TenantModel

from .base import MasterCrudRepository


class SqlTenantRepository(MasterCrudRepository[Tenant, UUID, TenantModel]):
    model = TenantModel

    def _key(self, tenant: Tenant) -> UUID:
        return tenant.id

    def _to_entity(self, row: TenantModel) -> Tenant:
        return Tenant(
            id=row.id,
            name=row.name,
            status=TenantStatus(row.status),
            created_at=row.created_at,
        )

    def _to_model(self, tenant: Tenant) -> TenantModel:
        return TenantModel(
            id=tenant.id,
            name=tenant.name,
            status=tenant.status.value,
            created_at=tenant.created_at,
        )

    def _apply(self, row: TenantModel, tenant: Tenant) -> None:
        row.name = tenant.name
        row.status = tenant.status.value
