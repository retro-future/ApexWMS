"""FR-1.2: rotate a refresh token into a new access+refresh pair.

Rotation chain: the presented token is revoked and linked to its
replacement. Presenting an *already-revoked* token means it leaked —
every live token for that user+tenant is revoked in response.
"""

import hmac
from uuid import UUID

from application.dtos import AuthTokens
from application.errors import InvalidTokenError, TenantNotActiveError
from application.ports import (
    Clock,
    MasterUnitOfWork,
    MembershipRepository,
    RefreshTokenRepository,
    TenantRepository,
    TokenService,
    UserRepository,
)
from application.use_cases.token_issuer import TokenIssuer
from domain.entities import MembershipKey
from domain.tenancy import TenantStatus


class RefreshTokens:
    def __init__(
        self,
        users: UserRepository,
        tenants: TenantRepository,
        memberships: MembershipRepository,
        refresh_tokens: RefreshTokenRepository,
        tokens: TokenService,
        issuer: TokenIssuer,
        clock: Clock,
        uow: MasterUnitOfWork,
    ) -> None:
        self._users = users
        self._tenants = tenants
        self._memberships = memberships
        self._refresh_tokens = refresh_tokens
        self._tokens = tokens
        self._issuer = issuer
        self._clock = clock
        self._uow = uow

    async def execute(self, refresh_token: str) -> AuthTokens:
        jti, secret = _parse(refresh_token)
        record = await self._refresh_tokens.get(jti)
        if record is None or not hmac.compare_digest(
            record.token_hash, self._tokens.hash_opaque(secret)
        ):
            raise InvalidTokenError()

        now = self._clock.now()
        if record.is_revoked:
            await self._refresh_tokens.revoke_all_for_user(record.user_id, record.tenant_id, now)
            await self._uow.commit()
            raise InvalidTokenError("refresh token reuse detected")
        if record.is_expired(now):
            raise InvalidTokenError()

        user = await self._users.get(record.user_id)
        # Role is re-read at rotation, so a role change takes effect at most
        # one access-token lifetime after it is made.
        membership = await self._memberships.get(MembershipKey(record.user_id, record.tenant_id))
        if user is None or not user.is_active or membership is None:
            raise InvalidTokenError()
        tenant = await self._tenants.get(record.tenant_id)
        if tenant is None or tenant.status is not TenantStatus.ACTIVE:
            raise TenantNotActiveError()

        pair, new_jti = await self._issuer.issue(user.id, record.tenant_id, membership.role)
        record.revoked_at = now
        record.replaced_by = new_jti
        await self._refresh_tokens.update(record)
        await self._uow.commit()
        return pair


def _parse(refresh_token: str) -> tuple[UUID, str]:
    jti_part, sep, secret = refresh_token.partition(".")
    if not sep or not secret:
        raise InvalidTokenError()
    try:
        return UUID(jti_part), secret
    except ValueError:
        raise InvalidTokenError() from None
