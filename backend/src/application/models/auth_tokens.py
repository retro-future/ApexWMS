"""Response payload for a refreshed access+refresh pair.

Distinct from ``application.dtos.AuthTokens``, the DI-context dataclass a
handler passes between collaborators before it ever reaches this wire shape.
"""

from __future__ import annotations

from application.core import CamelModel
from application.dtos import AuthTokens


class AuthTokensData(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

    @classmethod
    def from_entity(cls, tokens: AuthTokens) -> AuthTokensData:
        return cls(access_token=tokens.access_token, refresh_token=tokens.refresh_token)
