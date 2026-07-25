"""Issues an access+refresh pair and records the refresh token.

Shared by Login and RefreshTokens. Does not commit — the calling use case
owns the transaction boundary.

Both the record and the identity it belongs to are master-side, so this
touches one database regardless of which store the token ends up speaking
for. What the token *says* is decided by ``ClaimsFactory``.
"""

from uuid import UUID

from application.dtos import AuthTokens, IssuedClaims
from application.ports import Clock, RefreshTokenRepository, TokenService
from application.types import RefreshTokenTtl
from domain.entities import RefreshTokenRecord


class TokenIssuer:
    def __init__(
        self,
        tokens: TokenService,
        refresh_tokens: RefreshTokenRepository,
        clock: Clock,
        refresh_ttl: RefreshTokenTtl,
    ) -> None:
        self._tokens = tokens
        self._refresh_tokens = refresh_tokens
        self._clock = clock
        self._refresh_ttl = refresh_ttl

    async def issue(
        self, user_id: UUID, claims: IssuedClaims
    ) -> tuple[AuthTokens, UUID]:
        parts = self._tokens.issue_refresh()
        record = RefreshTokenRecord(
            id=parts.jti,
            user_id=user_id,
            token_hash=parts.token_hash,
            expires_at=self._clock.now() + self._refresh_ttl,
        )
        await self._refresh_tokens.add(record)
        access = self._tokens.issue_access(
            user_id, claims.tenant_id, claims.tenant_role, claims.app_roles
        )
        return AuthTokens(access, f"{parts.jti}.{parts.secret}"), parts.jti
