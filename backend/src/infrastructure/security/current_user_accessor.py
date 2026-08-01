"""Resolves the authenticated identity from the request's bearer token.

Backs ``AuthProvider`` (di/providers/auth.py), which only constructs this
and calls it — see docs/architecture/tenant-resolution.md for why this
shape mirrors ``CurrentTenantAccessor``.
"""

from application.dtos import CurrentUser
from application.errors import AuthenticationError
from domain.permissions import PermissionEvaluator
from infrastructure.security.request_claims import RequestBearerClaims


class CurrentUserAccessor:
    def __init__(self, claims: RequestBearerClaims, evaluator: PermissionEvaluator) -> None:
        self._claims = claims
        self._evaluator = evaluator

    def get_current_user(self) -> CurrentUser:
        claims = self._claims.get()
        if claims is None:
            raise AuthenticationError("missing bearer token")
        return CurrentUser(
            user_id=claims.user_id,
            permissions=self._evaluator.evaluate(claims.app_roles, claims.tenant_role),
            tenant_id=claims.tenant_id,
            tenant_role=claims.tenant_role,
            app_roles=claims.app_roles,
        )
