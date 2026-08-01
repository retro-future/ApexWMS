"""Authorization: the permission evaluator (APP scope).

Constructs the ``PermissionEvaluator`` from today's two static role
providers. A future DB-backed tenant role source only changes this one
``@provide`` method — nothing downstream (``CurrentUserAccessor``, the
evaluator itself) needs to know.
"""

from dishka import Provider, Scope, provide

from domain.permissions import (
    AppRolePermissionProvider,
    PermissionEvaluator,
    TenantRolePermissionProvider,
)


class AuthorizationProvider(Provider):
    scope = Scope.APP

    @provide
    def permission_evaluator(self) -> PermissionEvaluator:
        return PermissionEvaluator(
            AppRolePermissionProvider(), TenantRolePermissionProvider()
        )
