"""JWT access tokens and opaque refresh/invite secrets.

Access tokens are short-lived HS256 JWTs carrying exactly one tenant_id
(FR-1.3). Refresh and invite tokens are opaque high-entropy secrets;
only their sha256 is stored, and the wire format ``"{id}.{secret}"``
lets the row be found by id and verified by hash.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

import jwt

from application.dtos import RefreshTokenParts
from application.errors import InvalidTokenError
from application.ports import Clock
from domain.roles import Role

_ALGORITHM = "HS256"


@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: UUID
    tenant_id: UUID
    role: Role


class JwtTokenService:
    """Implements the application ``TokenService`` port, plus access-token
    decoding for the request-auth path (used by DI, not by use cases)."""

    def __init__(self, secret: str, access_ttl: timedelta, clock: Clock) -> None:
        self._secret = secret
        self._access_ttl = access_ttl
        self._clock = clock

    def issue_access(self, user_id: UUID, tenant_id: UUID, role: Role) -> str:
        now = self._clock.now()
        payload = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "role": role.value,
            "iat": int(now.timestamp()),
            "exp": int((now + self._access_ttl).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=_ALGORITHM)

    def decode_access(self, token: str) -> AccessClaims:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[_ALGORITHM])
            return AccessClaims(
                user_id=UUID(payload["sub"]),
                tenant_id=UUID(payload["tenant_id"]),
                role=Role(payload["role"]),
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
