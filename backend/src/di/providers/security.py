"""Security services: password hashing, token issuing, the clock (APP scope)."""

from datetime import timedelta

from dishka import Provider, Scope, alias, provide

from application.ports import Clock, PasswordHasher, TokenService
from infrastructure.clock import SystemClock
from infrastructure.config import Settings
from infrastructure.security.password import Argon2PasswordHasher
from infrastructure.security.tokens import JwtTokenService


class SecurityProvider(Provider):
    scope = Scope.APP

    @provide
    def clock(self) -> Clock:
        return SystemClock()

    @provide
    def password_hasher(self) -> PasswordHasher:
        return Argon2PasswordHasher()

    @provide
    def jwt_service(self, settings: Settings, clock: Clock) -> JwtTokenService:
        return JwtTokenService(
            secret=settings.jwt_secret,
            access_ttl=timedelta(minutes=settings.access_token_ttl_minutes),
            clock=clock,
        )

    token_service = alias(source=JwtTokenService, provides=TokenService)
