"""Issues an access+refresh pair and records the refresh token.

Shared by SignUp, Login, and RefreshTokens. Does not commit — the
calling use case owns the transaction boundary.
"""

from datetime import timedelta
from uuid import UUID

from application.dtos import AuthTokens
from application.ports import Clock, RefreshTokenRepository, TokenService
from domain.entities import RefreshTokenRecord
from domain.roles import Role


class TokenIssuer:
    def __init__(
        self,
        tokens: TokenService,
        refresh_tokens: RefreshTokenRepository,
        clock: Clock,
        refresh_ttl: timedelta,
    ) -> None:
        self._tokens = tokens
        self._refresh_tokens = refresh_tokens
        self._clock = clock
        self._refresh_ttl = refresh_ttl

    async def issue(self, user_id: UUID, tenant_id: UUID, role: Role) -> tuple[AuthTokens, UUID]:
        parts = self._tokens.issue_refresh()
        record = RefreshTokenRecord(
            id=parts.jti,
            user_id=user_id,
            tenant_id=tenant_id,
            token_hash=parts.token_hash,
            expires_at=self._clock.now() + self._refresh_ttl,
        )
        await self._refresh_tokens.add(record)
        access = self._tokens.issue_access(user_id, tenant_id, role)
        return AuthTokens(access, f"{parts.jti}.{parts.secret}"), parts.jti
