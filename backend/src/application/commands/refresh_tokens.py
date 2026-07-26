"""FR-1.2: rotate a refresh token into a new access+refresh pair.

Rotation chain: the presented token is revoked and linked to its
replacement. Presenting an *already-revoked* token means it leaked —
every live token for that user is revoked in response.

Tokens and identities are both master-side, so rotation touches one
database. Claims are rebuilt from scratch on every rotation, which is how
a role change or a revoked tenant access takes effect at most one
access-token lifetime after it is made.
"""

import hmac
from uuid import UUID

from application.core import CamelModel, Command, IRequestHandler, ResultWithData
from application.dtos import RequestedTenant
from application.errors import InvalidTokenError
from application.ports import (
    Clock,
    MasterUnitOfWork,
    RefreshTokenRepository,
    TokenService,
    UserRepository,
)
from application.services.claims import ClaimsFactory
from application.services.token_issuer import TokenIssuer


class AuthTokensData(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokensCommand(Command[ResultWithData[AuthTokensData]]):
    refresh_token: str


class RefreshTokensHandler(
    IRequestHandler[ResultWithData[AuthTokensData], RefreshTokensCommand]
):
    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        tokens: TokenService,
        claims: ClaimsFactory,
        issuer: TokenIssuer,
        clock: Clock,
        uow: MasterUnitOfWork,
        requested: RequestedTenant,
    ) -> None:
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._tokens = tokens
        self._claims = claims
        self._issuer = issuer
        self._clock = clock
        self._uow = uow
        self._requested_tenant_id = requested.tenant_id

    async def handle(
        self, request: RefreshTokensCommand
    ) -> ResultWithData[AuthTokensData]:
        jti, secret = _parse(request.refresh_token)
        record = await self._refresh_tokens.get(jti)
        if record is None or not hmac.compare_digest(
            record.token_hash, self._tokens.hash_opaque(secret)
        ):
            raise InvalidTokenError()

        now = self._clock.now()
        if record.is_revoked:
            await self._refresh_tokens.revoke_all_for_user(record.user_id, now)
            await self._uow.commit()
            raise InvalidTokenError("refresh token reuse detected")
        if record.is_expired(now):
            raise InvalidTokenError()

        user = await self._users.get(record.user_id)
        if user is None or not user.is_active:
            raise InvalidTokenError()

        claims = await self._claims.build(user, self._requested_tenant_id)
        pair, new_jti = await self._issuer.issue(user.id, claims)
        record.revoked_at = now
        record.replaced_by = new_jti
        await self._refresh_tokens.update(record)
        await self._uow.commit()
        return ResultWithData[AuthTokensData].succeed_with_data(
            AuthTokensData(access_token=pair.access_token, refresh_token=pair.refresh_token)
        )


def _parse(refresh_token: str) -> tuple[UUID, str]:
    jti_part, sep, secret = refresh_token.partition(".")
    if not sep or not secret:
        raise InvalidTokenError()
    try:
        return UUID(jti_part), secret
    except ValueError:
        raise InvalidTokenError() from None
