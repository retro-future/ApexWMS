"""Tenant provisioning port (PRD §3.4)."""

from typing import Protocol
from uuid import UUID


class TenantProvisioner(Protocol):
    async def provision(self, tenant_id: UUID, timezone: str) -> None:
        """Drive the tenant to ACTIVE, or leave it FAILED and raise.

        Idempotent: safe to call again on a FAILED tenant.
        Raises ProvisioningFailedError on failure.
        """
        ...
