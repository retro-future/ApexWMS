"""JWT access tokens and opaque refresh/invite secrets.

An access token carries at most one tenant (FR-1.3). A platform operator's
token carries **no** ``tenant`` claim at all rather than a null one — the
absence is what marks them as belonging to no store, and it is what the
claims factory decided (PRD §3.3).

Refresh and invite tokens are opaque high-entropy secrets; only their
sha256 is stored, and the wire format ``"{id}.{secret}"`` lets the row be
found by id and verified by hash.
"""

import hashlib
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

import jwt

from application.dtos import RefreshTokenParts
from application.errors import InvalidTokenError
from application.ports import Clock
from domain.enums import AppRole, TenantRole


@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: UUID
    tenant_id: UUID | None
    tenant_role: TenantRole | None
    app_roles: tuple[AppRole, ...]


class JwtTokenService:
    """Implements the application ``TokenService`` port, plus access-token
    decoding for the request-auth path (used by DI, not by use cases)."""

    _ALGORITHM = "HS256"

    def __init__(self, secret: str, access_ttl: timedelta, clock: Clock) -> None:
        self._secret = secret
        self._access_ttl = access_ttl
        self._clock = clock

    def issue_access(
        self,
        user_id: UUID,
        tenant_id: UUID | None,
        tenant_role: TenantRole | None,
        app_roles: Sequence[AppRole] = (),
    ) -> str:
        now = self._clock.now()
        payload: dict[str, object] = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int((now + self._access_ttl).timestamp()),
        }
        if app_roles:
            payload["app_roles"] = [role.value for role in app_roles]
        if tenant_id is not None and tenant_role is not None:
            payload["tenant"] = str(tenant_id)
            payload["role"] = tenant_role.value
        return jwt.encode(payload, self._secret, algorithm=self._ALGORITHM)

    def decode_access(self, token: str) -> AccessClaims:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._ALGORITHM])
            tenant = payload.get("tenant")
            role = payload.get("role")
            return AccessClaims(
                user_id=UUID(payload["sub"]),
                tenant_id=UUID(tenant) if tenant else None,
                tenant_role=TenantRole(role) if role else None,
                app_roles=tuple(
                    AppRole(value) for value in payload.get("app_roles", [])
                ),
            )
        except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
            raise InvalidTokenError() from exc

    def issue_refresh(self) -> RefreshTokenParts:
        secret = self.new_opaque_secret()
        return RefreshTokenParts(jti=uuid4(), secret=secret, token_hash=self.hash_opaque(secret))

    def new_opaque_secret(self) -> str:
        return secrets.token_urlsafe(32)

    def hash_opaque(self, secret: str) -> str:
        return hashlib.sha256(secret.encode()).hexdigest()
