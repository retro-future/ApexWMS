"""Application-internal DTOs — frozen dataclasses that never cross an HTTP
boundary: DI-context values (``CurrentUser``, ``RequestedTenant``) and
carriers passed between collaborator services (``ClaimsFactory``,
``TokenIssuer``). CQRS messages — commands, queries, and their result
payloads — are Pydantic models instead, defined alongside their handler in
``application/commands/``/``application/queries/`` (see ``application/core/``
for the shared base classes). The split is by role, not by layer: does this
object cross a message boundary that needs structural validation and JSON
shape, or does it just carry context through the DI graph?
"""

from application.dtos.auth_tokens import AuthTokens
from application.dtos.current_user import CurrentUser
from application.dtos.issued_claims import IssuedClaims
from application.dtos.owner_seed import OwnerSeed
from application.dtos.posting_entry import MoneyEffect, Posting, PostingEntry
from application.dtos.refresh_token_parts import RefreshTokenParts
from application.dtos.requested_tenant import RequestedTenant

__all__ = [
    "AuthTokens",
    "CurrentUser",
    "IssuedClaims",
    "MoneyEffect",
    "OwnerSeed",
    "Posting",
    "PostingEntry",
    "RefreshTokenParts",
    "RequestedTenant",
]
