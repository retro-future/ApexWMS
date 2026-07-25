"""A platform role held by a user (PRD §3.1).

The port of ASP.NET Identity's ``user_roles`` join table: a SuperAdmin is
not a separate kind of entity, just a ``User`` with ``app.superadmin``
assigned here. Modelled as a join rather than a column because a person
can hold more than one platform role.

Uniqueness of ``(user_id, role)`` is a database constraint, not the
primary key — see the unique index in the master migration. The surrogate
id keeps this entity in the same shape as every other one, so the generic
``Repository[E, UUID]`` works for it unmodified.
"""

from dataclasses import dataclass
from uuid import UUID

from domain.core import MasterEntity, UuidEntity
from domain.roles import AppRole


@dataclass(eq=False, kw_only=True)
class UserAppRole(UuidEntity, MasterEntity):
    user_id: UUID
    role: AppRole
