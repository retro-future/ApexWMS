"""Opening a tenant's database from outside a tenant-scoped request.

The port of the C# reference's ``tenantUow.SetCurrentTenantByIdAsync`` —
a way to reach into one tenant's database when the tenant was discovered
*during* the operation rather than resolved at the edge.

Login is the case that needs it: the tenant comes from the master ``User``
row, which is only read once the password has been checked, so the
request-scoped ``TenantSession`` (which needs the tenant up front) cannot
serve it. Accepting an invitation is the other.

This is deliberately narrow. Ordinary tenant-scoped requests keep using the
edge-resolved session — nothing here is a licence to open arbitrary tenant
databases mid-request.
"""

from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from application.ports.tenant.repositories import EmployeeRepository
from application.ports.uow import UnitOfWork


class TenantWorkspace(Protocol):
    """A live session on one tenant's database."""

    @property
    def employees(self) -> EmployeeRepository: ...

    @property
    def uow(self) -> UnitOfWork: ...


class TenantScope(Protocol):
    def for_tenant(
        self, tenant_id: UUID
    ) -> AbstractAsyncContextManager[TenantWorkspace]:
        """Open the named tenant's database for the duration of the block.

        Raises ``TenantNotActiveError`` if the tenant is not ACTIVE, so a
        suspended store cannot be reached by this path either.
        """
        ...
