"""Decodes the request's bearer token once, shared by identity and tenant
resolution (``CurrentUserAccessor``, ``CurrentTenantAccessor``) so the token
is decoded at most once per request instead of independently by each.
"""

from fastapi import Request

from infrastructure.security.tokens import AccessClaims, JwtTokenService


class RequestBearerClaims:
    """The request's decoded bearer token, or ``None`` on an anonymous
    request.

    A malformed token still raises ``InvalidTokenError`` (via
    ``JwtTokenService.decode_access``) — an unreadable ``Authorization``
    header is an error, not an anonymous request.
    """

    def __init__(self, request: Request, tokens: JwtTokenService) -> None:
        self._request = request
        self._tokens = tokens
        self._claims: AccessClaims | None = None
        # A separate flag rather than a sentinel object: None is itself a
        # valid decoded result (an anonymous request), and widening the
        # field to hold a sentinel would lose the type it actually carries.
        self._decoded = False

    def get(self) -> AccessClaims | None:
        if not self._decoded:
            self._claims = self._decode()
            self._decoded = True
        return self._claims

    def _decode(self) -> AccessClaims | None:
        scheme, _, token = self._request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return None
        return self._tokens.decode_access(token.strip())
