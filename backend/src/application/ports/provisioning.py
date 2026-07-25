"""Tenant provisioning port (PRD §3.4)."""

from typing import Protocol
from uuid import UUID

from application.dtos import OwnerSeed


class TenantProvisioner(Protocol):
    async def provision(
        self, tenant_id: UUID, timezone: str, owner: OwnerSeed | None = None
    ) -> None:
        """Drive the tenant to ACTIVE, or leave it FAILED and raise.

        Creates the database, migrates it, and seeds it — including the
        Owner's ``Employee`` row, which is the only way into a freshly
        created tenant now that sign-up is gone. The matching master ``User``
        is written by the caller, which is why ``OwnerSeed`` carries its id.

        ``owner`` is None only when re-provisioning a tenant that already has
        one. Idempotent: safe to call again on a FAILED tenant.
        Raises ProvisioningFailedError on failure.
        """
        ...
