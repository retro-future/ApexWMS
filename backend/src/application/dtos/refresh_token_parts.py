"""A freshly generated refresh token, before persistence."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RefreshTokenParts:
    """A freshly generated refresh token, before persistence.

    The wire format is ``"{jti}.{secret}"``; only ``token_hash`` is stored.
    """

    jti: UUID
    secret: str
    token_hash: str
