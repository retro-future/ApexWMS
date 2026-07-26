"""Deciding what a freshly issued token says (PRD §3.3).

The port of the C# reference's ``UserCustomClaimsFactory``. The key
property is that **the client never decides which tenant a token speaks
for** — the server does, from the database:

    tenant_id = requested (X-Tenant) ?? user.tenant_id

A requested tenant is honoured only if the user actually has access to it,
so a header cannot widen anyone's reach. With no tenant either way the
subject is a platform operator and the token carries no tenant claim at
all, rather than a null one.

The tenant role is read from that store's own ``employees`` table, which is
why this needs ``TenantScope`` rather than a request-scoped session: at
login the tenant is not known until the master user row has been read.
"""

from uuid import UUID

from application.dtos import IssuedClaims
from application.errors import AuthorizationError, InvalidCredentialsError
from application.ports import (
    TenantScope,
    UserAppRoleRepository,
    UserTenantAccessRepository,
)
from domain.entities import User


class ClaimsFactory:
    def __init__(
        self,
        app_roles: UserAppRoleRepository,
        access: UserTenantAccessRepository,
        scope: TenantScope,
    ) -> None:
        self._app_roles = app_roles
        self._access = access
        self._scope = scope

    async def build(
        self, user: User, requested_tenant_id: UUID | None = None
    ) -> IssuedClaims:
        granted = tuple(
            assignment.role for assignment in await self._app_roles.list_for_user(user.id)
        )

        tenant_id = requested_tenant_id or user.tenant_id
        if tenant_id is None:
            return IssuedClaims(tenant_id=None, tenant_role=None, app_roles=granted)

        if tenant_id != user.tenant_id and not await self._access.exists(
            user.id, tenant_id
        ):
            raise AuthorizationError("no access to the requested tenant")

        async with self._scope.for_tenant(tenant_id) as workspace:
            employee = await workspace.employees.get(user.id)

        if employee is None or not employee.is_active:
            # The master account is fine but there is no active presence at
            # this store — indistinguishable from bad credentials on purpose.
            raise InvalidCredentialsError()

        return IssuedClaims(
            tenant_id=tenant_id, tenant_role=employee.role, app_roles=granted
        )
