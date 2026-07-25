"""A person's presence at one store: their role there (PRD §3.1).

Lives in that store's own database, so it carries no ``tenant_id`` — the
database it is stored in *is* the store.

**``Employee.id`` is the master ``User.id``**, not a fresh identifier.
That is what lets tenant-side rows — from M3, ``stock_movements.user_id``
and ``documents.created_by`` — be real foreign keys into a tenant-local
table while the login identity stays central. Breaking that equality
silently breaks every ledger join.

``email`` and ``full_name`` are copied from the User. Denormalized on
purpose: listing a store's staff, and later joining the ledger to a name,
must not require a cross-database read. MasterDB stays the source of
truth if the two ever disagree.
"""

from dataclasses import dataclass
from datetime import datetime

from domain.core import TenantEntity, UuidEntity
from domain.roles import TenantRole


@dataclass(eq=False, kw_only=True)
class Employee(UuidEntity, TenantEntity):
    # Inherited `id` is the master User.id — see the module docstring.
    email: str
    full_name: str
    role: TenantRole
    is_active: bool
    created_at: datetime
