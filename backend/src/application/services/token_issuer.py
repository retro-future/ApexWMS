"""Issues an access+refresh pair and records the refresh token, and revokes
every live token for a user.

Shared by ``LoginHandler``, ``RefreshTokensHandler`` and
``ChangePasswordHandler``. Does not commit — the calling handler owns the
transaction boundary.

Both the record and the identity it belongs to are master-side, so this
touches one database regardless of which store the token ends up speaking
for. What the token *says* is decided by ``ClaimsFactory``.
"""

from datetime import datetime
from uuid import UUID

from application.common.repository import MasterDbRepository
from application.dtos import AuthTokens, IssuedClaims
from application.ports import Clock, TokenService
from application.specs import LiveTokensForUser
from application.types import RefreshTokenTtl
from domain.entities import RefreshTokenRecord
from infrastructure.persistence.master.models import RefreshTokenModel


class TokenIssuer:
    def __init__(
        self,
        tokens: TokenService,
        refresh_tokens: MasterDbRepository[RefreshTokenRecord, RefreshTokenModel],
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

    async def revoke_all_for_user(self, user_id: UUID, now: datetime) -> None:
        """Revoke every not-yet-revoked token for the user — the
        reuse-detection response, and what a password change triggers."""
        for token in await self._refresh_tokens.find(LiveTokensForUser(user_id)):
            token.revoked_at = now
            await self._refresh_tokens.update(token)
