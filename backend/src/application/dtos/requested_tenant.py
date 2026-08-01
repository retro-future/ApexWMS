"""The store an ``X-Tenant`` header asked for, if any (PRD §3.3)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RequestedTenant:
    """The store an ``X-Tenant`` header asked for, if any (PRD §3.3).

    Resolved from a slug or a UUID at the edge, but *not* authorized there:
    on the anonymous auth routes there is no identity yet to authorize
    against. ``ClaimsFactory`` makes that check once the user is known.
    """

    tenant_id: UUID | None = None
