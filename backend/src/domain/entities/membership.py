"""Which user belongs to which tenant, with which role (PRD §3.1)."""

from dataclasses import dataclass
from typing import NamedTuple
from uuid import UUID

from domain.core import MasterEntity
from domain.roles import Role


class MembershipKey(NamedTuple):
    """The composite primary key (user_id, tenant_id).

    A tuple subclass on purpose: SQLAlchemy accepts it verbatim as a
    composite identity, and the field order here must match the primary
    key column order on the persistence model.
    """

    user_id: UUID
    tenant_id: UUID


@dataclass(kw_only=True)
class Membership(MasterEntity):
    """Keyed by ``MembershipKey`` — no identity of its own.

    Not a UuidEntity: the row has a composite primary key and no surrogate
    id, so field-wise equality is the correct semantics here.
    """

    user_id: UUID
    tenant_id: UUID
    role: Role

    @property
    def key(self) -> MembershipKey:
        return MembershipKey(self.user_id, self.tenant_id)
