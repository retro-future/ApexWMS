"""The domain service that resolves effective permissions.

Kept separate from the providers it depends on (``providers.py``) and the
catalog they draw from (``catalog.py``) — the evaluator has no idea whether
a provider is the two static ones defined today or a future DB-backed
tenant role source; it only knows the ``RolePermissionProvider`` Protocol.
"""

from collections.abc import Iterable

from domain.permissions.catalog import Permission
from domain.permissions.providers import (
    AppRolePermissionProvider,
    RolePermissionProvider,
    TenantRolePermissionProvider,
)


class PermissionEvaluator:
    """Resolves the effective permission set for a holder of app/tenant roles.

    App and tenant roles are additive: a SuperAdmin who is also an Owner
    somewhere holds the union, and each half is drawn from the same catalog.
    """

    def __init__(
        self,
        app_role_provider: RolePermissionProvider,
        tenant_role_provider: RolePermissionProvider,
    ) -> None:
        self._app_role_provider = app_role_provider
        self._tenant_role_provider = tenant_role_provider

    def evaluate(
        self, app_roles: Iterable[str] = (), tenant_role: str | None = None
    ) -> frozenset[Permission]:
        granted: set[Permission] = set()
        for role in app_roles:
            granted |= self._app_role_provider.get_permissions_for_role(role)
        if tenant_role is not None:
            granted |= self._tenant_role_provider.get_permissions_for_role(tenant_role)
        return frozenset(granted)


def permissions_for(
    app_roles: Iterable[str] = (), tenant_role: str | None = None
) -> frozenset[Permission]:
    """Domain-layer convenience: evaluate with the static providers, no DI
    container required. Production code prefers an injected
    ``PermissionEvaluator`` (see ``di/providers/authorization.py``); this
    exists for domain-only callers and tests.
    """
    return _default_evaluator.evaluate(app_roles, tenant_role)


_default_evaluator = PermissionEvaluator(
    AppRolePermissionProvider(), TenantRolePermissionProvider()
)
