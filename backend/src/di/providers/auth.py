"""Request authentication: bearer token → ``CurrentUser`` (REQUEST scope).

Anything downstream that depends on ``CurrentUser`` — including the
tenant session — is unreachable without a valid token; the 401 falls out
of dependency resolution, not per-route boilerplate.
"""

from dishka import Provider, Scope, provide
from fastapi import Request

from application.dtos import CurrentUser
from application.errors import AuthenticationError
from infrastructure.security.tokens import JwtTokenService


class AuthProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def current_user(self, request: Request, tokens: JwtTokenService) -> CurrentUser:
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise AuthenticationError("missing bearer token")
        claims = tokens.decode_access(token.strip())
        return CurrentUser(
            user_id=claims.user_id, tenant_id=claims.tenant_id, role=claims.role
        )
