"""Resolves the tenant a request is acting on (PRD §3.3).

The one resolver for naming/authorizing a tenant — see
docs/architecture/tenant-resolution.md. Modeled on the reference
``ICurrentTenantAccessor``: a single class with private helper methods per
resolution step, backing ``TenantDbProvider`` (di/providers/tenant_db.py),
which only constructs this and delegates.

Tenant resolution is a two-tier fallback, ported from the C# reference
minus its MCP tier:

  1. ``X-Tenant`` header — a slug or a UUID;
  2. the JWT ``tenant`` claim, stamped at login from ``users.tenant_id``.

**The header wins over the claim.** That asymmetry is deliberate: it is
what lets someone with accounts at several stores switch between them
without re-authenticating — the token proves *who* they are, the header
decides *whose data* they are looking at.

The reference trusts the header outright and relies on the tenant database
returning nothing for an unauthorized user. We do not: a header naming a
store the caller has no grant for is a 403 here, before any session opens.
"""

from uuid import UUID

from fastapi import Request
from sqlalchemy import select

from application.dtos import RequestedTenant
from application.errors import (
    AuthorizationError,
    MissingTenantError,
    TenantNotActiveError,
    TenantNotFoundError,
)
from domain.enums import TenantStatus
from infrastructure.config import Settings
from infrastructure.persistence.master.models import (
    TenantDatabaseModel,
    TenantModel,
    UserTenantAccessModel,
)
from infrastructure.security.request_claims import RequestBearerClaims
from infrastructure.tenancy import TenantContext, tenant_db_url
from infrastructure.types import MasterSession


class CurrentTenantAccessor:
    TENANT_HEADER = "X-Tenant"

    def __init__(
        self,
        request: Request,
        master: MasterSession,
        settings: Settings,
        claims: RequestBearerClaims,
    ) -> None:
        self._request = request
        self._master = master
        self._settings = settings
        self._claims = claims

    async def get_current_tenant(self) -> TenantContext:
        tenant = await self._resolve_tenant_model()
        if tenant.status != TenantStatus.ACTIVE.value:
            raise TenantNotActiveError()
        database = await self._master.get(TenantDatabaseModel, tenant.id)
        if database is None:
            raise TenantNotActiveError()
        return TenantContext(
            tenant_id=str(tenant.id),
            db_url=tenant_db_url(self._settings.master_db_url, database.db_name),
        )

    async def get_requested_tenant(self) -> RequestedTenant:
        """The header's tenant for routes that merely *accept* one.

        Unlike ``get_current_tenant`` this never raises for an absent
        header — login works without one — and performs no access check,
        because on an anonymous route there is no identity yet to check
        against.
        """
        value = self._header_value()
        if not value:
            return RequestedTenant()
        tenant = await self._by_slug_or_id(value)
        if tenant is None:
            raise TenantNotFoundError()
        return RequestedTenant(tenant_id=tenant.id)

    async def _resolve_tenant_model(self) -> TenantModel:
        claims = self._claims.get()
        requested = self._header_value()

        # Tier 2: no X-Tenant header, fall back to the JWT tenant claim.
        if not requested:
            if claims is None or claims.tenant_id is None:
                raise MissingTenantError(
                    f"name the tenant with a {self.TENANT_HEADER} header or a token "
                    "carrying a tenant claim"
                )
            tenant = await self._master.get(TenantModel, claims.tenant_id)
            if tenant is None:
                raise TenantNotFoundError()
            return tenant

        # Tier 1: X-Tenant header present, it wins over the claim.
        tenant = await self._by_slug_or_id(requested)
        if tenant is None:
            raise TenantNotFoundError()
        if claims is not None and claims.tenant_id != tenant.id:
            # Switching stores: allowed only where a grant exists. Checked
            # here rather than left to an empty result set.
            await self._authorize_switch(claims.user_id, tenant.id)
        return tenant

    async def _authorize_switch(self, user_id: UUID, tenant_id: UUID) -> None:
        granted = await self._master.scalar(
            select(UserTenantAccessModel.id).where(
                UserTenantAccessModel.user_id == user_id,
                UserTenantAccessModel.tenant_id == tenant_id,
            )
        )
        if granted is None:
            raise AuthorizationError("no access to the requested tenant")

    async def _by_slug_or_id(self, value: str) -> TenantModel | None:
        """The header accepts either form, as the C# reference's does."""
        try:
            return await self._master.get(TenantModel, UUID(value))
        except ValueError:
            return await self._master.scalar(
                select(TenantModel).where(TenantModel.slug == value)
            )

    def _header_value(self) -> str:
        return self._request.headers.get(self.TENANT_HEADER, "").strip().lower()
