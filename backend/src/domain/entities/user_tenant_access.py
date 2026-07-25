"""Which stores a user may act in, beyond their home store (PRD §3.3).

``User.tenant_id`` names the store whose claim is stamped at login. This
table is what lets one person hold accounts at several stores and switch
between them with the ``X-Tenant`` header *without re-authenticating* —
the token proves who they are, the header decides whose data they are
looking at.

It is also the authorization check on that header: a header naming a
store the user has no row for is refused, rather than trusted and left to
return an empty result.

Uniqueness of ``(user_id, tenant_id)`` is a database constraint, not the
primary key — see the unique index in the master migration.
"""

from dataclasses import dataclass
from uuid import UUID

from domain.core import MasterEntity, UuidEntity


@dataclass(eq=False, kw_only=True)
class UserTenantAccess(UuidEntity, MasterEntity):
    user_id: UUID
    tenant_id: UUID
