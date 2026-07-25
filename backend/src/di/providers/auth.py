"""Request authentication: bearer token → ``CurrentUser`` (REQUEST scope).

Anything downstream that depends on ``CurrentUser`` is unreachable without
a valid token; the 401 falls out of dependency resolution, not per-route
boilerplate.

All resolution logic lives in ``CurrentUserAccessor``
(infrastructure/security/current_user_accessor.py) — this provider only
constructs collaborators and delegates (.claude/rules/backend/providers.md).
"""

from dishka import Provider, Scope, provide
from fastapi import Request

from application.dtos import CurrentUser
from infrastructure.security.current_user_accessor import CurrentUserAccessor
from infrastructure.security.request_claims import RequestBearerClaims
from infrastructure.security.tokens import JwtTokenService


class AuthProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def bearer_claims(self, request: Request, tokens: JwtTokenService) -> RequestBearerClaims:
        return RequestBearerClaims(request, tokens)

    @provide(scope=Scope.REQUEST)
    def current_user_accessor(self, claims: RequestBearerClaims) -> CurrentUserAccessor:
        return CurrentUserAccessor(claims)

    @provide(scope=Scope.REQUEST)
    def current_user(self, accessor: CurrentUserAccessor) -> CurrentUser:
        return accessor.get_current_user()
