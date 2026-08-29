"""The reads the tenant-registry use cases need, one class each.

Written against ``TenantModel`` (MasterDB), not ``Tenant`` (ADR 0007). The
by-slug read and the slug uniqueness probe are inline in the handlers.
"""

from uuid import UUID

from application.common.specification import Specification
from infrastructure.persistence.master.models import TenantModel


class TenantForWrite(Specification[TenantModel]):
    def __init__(self, tenant_id: UUID) -> None:
        super().__init__(TenantModel)
        self.tenant_id = tenant_id
        self.where(TenantModel.id == tenant_id)
        self.lock()
