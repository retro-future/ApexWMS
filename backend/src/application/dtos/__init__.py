"""Application-internal DTOs — frozen dataclasses that never cross an HTTP
boundary: DI-context values (``CurrentUser``, ``RequestedTenant``) and
carriers passed between collaborator services (``ClaimsFactory``,
``TokenIssuer``). CQRS messages are Pydantic models instead (see
``application/core/`` for the shared base classes): a ``Command``/``Query``
request shape is defined alongside its handler in
``application/commands/``/``application/queries/``, while its *response*
payload (a ``Result``/``PagedResult``'s ``TData``) lives in
``application/models/`` — see that package's docstring and
``.claude/rules/backend/cqrs-response-models.md``. The split from this
package is by role, not by layer: does this object cross a message boundary
that needs structural validation and JSON shape, or does it just carry
context through the DI graph?
"""

from application.dtos.auth_tokens import AuthTokens
from application.dtos.current_user import CurrentUser
from application.dtos.issued_claims import IssuedClaims
from application.dtos.line_input import LineInput
from application.dtos.owner_seed import OwnerSeed
from application.dtos.posting_entry import MoneyEffect, Posting, PostingEntry
from application.dtos.refresh_token_parts import RefreshTokenParts
from application.dtos.requested_tenant import RequestedTenant

__all__ = [
    "AuthTokens",
    "CurrentUser",
    "IssuedClaims",
    "LineInput",
    "MoneyEffect",
    "OwnerSeed",
    "Posting",
    "PostingEntry",
    "RefreshTokenParts",
    "RequestedTenant",
]
